# /opt/qrfacile/qrfacile_app/publish_routes.py
import time

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.auth_core import require_any_role

router = APIRouter()


def now() -> int:
    return int(time.time())


def _admin_active_winery_id(cur, user_id: int) -> int | None:
    cur.execute(
        "SELECT admin_active_winery_id FROM users WHERE id=%s LIMIT 1",
        (int(user_id),),
    )
    r = cur.fetchone() or {}
    wid = r.get("admin_active_winery_id")
    return int(wid) if wid else None


def _load_wine(cur, wine_id: int) -> dict:
    cur.execute(
        """
        SELECT
          qw.id AS wine_id,
          qw.winery_id,
          qw.qr_item_id,
          qw.wine_name,
          w.owner_user_id
        FROM qr_wines qw
        JOIN wineries w ON w.id = qw.winery_id
        WHERE qw.id=%s
        LIMIT 1
        """,
        (int(wine_id),),
    )
    r = cur.fetchone()

    if not r:
        raise HTTPException(404, "Lotto non trovato")

    return r


def _can_publish(user: dict, wine_row: dict, cur) -> bool:
    role = (user.get("role") or "").lower().strip()

    if role == "studio":
        return False

    if role == "winery":
        return int(user["id"]) == int(wine_row["owner_user_id"])

    if role == "admin":
        active = _admin_active_winery_id(cur, int(user["id"]))
        if not active:
            return False
        return int(active) == int(wine_row["winery_id"])

    return False


def _set_qr_status(cur, qr_item_id: int, status: str):
    cur.execute(
        """
        UPDATE qr_items
        SET status=%s, updated_at=%s
        WHERE id=%s
        """,
        (status, now(), int(qr_item_id)),
    )


def _set_labels_public(cur, wine_id: int, enabled: bool):
    ts = now()

    if enabled:
        cur.execute(
            """
            UPDATE wine_labels
            SET public_enabled=TRUE, published_at=%s, updated_at=%s
            WHERE wine_id=%s
            """,
            (ts, ts, int(wine_id)),
        )
    else:
        cur.execute(
            """
            UPDATE wine_labels
            SET public_enabled=FALSE, updated_at=%s
            WHERE wine_id=%s
            """,
            (ts, int(wine_id)),
        )


def _publication_missing_fields(cur, wine_id: int) -> list[str]:
    missing: list[str] = []

    cur.execute(
        """
        SELECT COUNT(*)::int AS cnt
        FROM wine_ingredients
        WHERE wine_id=%s
        """,
        (int(wine_id),),
    )
    ingredient_count = int((cur.fetchone() or {}).get("cnt") or 0)

    cur.execute(
        """
        SELECT COALESCE(extra_ingredients, '') AS extra_ingredients
        FROM wine_meta
        WHERE wine_id=%s
        LIMIT 1
        """,
        (int(wine_id),),
    )
    meta = cur.fetchone() or {}
    extra_ingredients = (meta.get("extra_ingredients") or "").strip()

    if ingredient_count <= 0 and not extra_ingredients:
        missing.append("ingredienti")

    cur.execute(
        """
        SELECT COUNT(*)::int AS cnt
        FROM wine_allergens
        WHERE wine_id=%s
        """,
        (int(wine_id),),
    )
    allergen_count = int((cur.fetchone() or {}).get("cnt") or 0)

    cur.execute(
        """
        SELECT contains_sulfites, contains_egg, contains_milk
        FROM qr_wines
        WHERE id=%s
        LIMIT 1
        """,
        (int(wine_id),),
    )
    flags = cur.fetchone() or {}

    has_allergen_flag = (
        bool(flags.get("contains_sulfites"))
        or bool(flags.get("contains_egg"))
        or bool(flags.get("contains_milk"))
    )

    if allergen_count <= 0 and not has_allergen_flag:
        missing.append("allergeni")

    cur.execute(
        """
        SELECT energy_kj, energy_kcal
        FROM wine_nutrition
        WHERE wine_id=%s
        LIMIT 1
        """,
        (int(wine_id),),
    )
    nut = cur.fetchone() or {}

    if nut.get("energy_kj") is None:
        missing.append("energia kJ")

    if nut.get("energy_kcal") is None:
        missing.append("energia kcal")

    cur.execute(
        """
        SELECT COUNT(*)::int AS cnt
        FROM wine_recycle_items
        WHERE wine_id=%s
          AND COALESCE(code, '') <> ''
        """,
        (int(wine_id),),
    )
    recycle_count = int((cur.fetchone() or {}).get("cnt") or 0)

    if recycle_count <= 0:
        missing.append("riciclabilità")

    return missing


def _quote_msg(text: str) -> str:
    return (
        text.replace(" ", "%20")
            .replace(",", "%2C")
            .replace(":", "%3A")
            .replace("/", "%2F")
    )


def _upsert_override_request(
    cur,
    wine_id: int,
    winery_id: int,
    user_id: int,
    missing_fields: list[str],
    reason: str,
):
    ts = now()
    missing_text = ", ".join(missing_fields)

    cur.execute(
        """
        SELECT id
        FROM publish_override_requests
        WHERE wine_id=%s
          AND status='pending'
        ORDER BY id DESC
        LIMIT 1
        """,
        (int(wine_id),),
    )
    existing = cur.fetchone()

    if existing:
        cur.execute(
            """
            UPDATE publish_override_requests
            SET missing_fields=%s,
                reason=%s,
                updated_at=%s
            WHERE id=%s
            """,
            (
                missing_text,
                (reason or "").strip(),
                ts,
                int(existing["id"]),
            ),
        )
        return int(existing["id"])

    cur.execute(
        """
        INSERT INTO publish_override_requests (
            wine_id,
            winery_id,
            requested_by_user_id,
            status,
            missing_fields,
            reason,
            created_at,
            updated_at
        )
        VALUES (%s,%s,%s,'pending',%s,%s,%s,%s)
        RETURNING id
        """,
        (
            int(wine_id),
            int(winery_id),
            int(user_id),
            missing_text,
            (reason or "").strip(),
            ts,
            ts,
        ),
    )
    return int(cur.fetchone()["id"])


@router.post("/app/wine/{wine_id}/publish")
def publish_wine(request: Request, wine_id: int, force: str = Form("")):
    user = require_any_role(request, ("winery", "studio", "admin"))

    role = (user.get("role") or "").lower().strip()
    force_publish = (force or "").strip() == "1"

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _load_wine(cur, int(wine_id))

            if not _can_publish(user, w, cur):
                raise HTTPException(403, "Forbidden")

            missing = _publication_missing_fields(cur, int(wine_id))

            if missing and not force_publish:
                msg = "Pubblicazione bloccata. Mancano dati obbligatori: " + ", ".join(missing)
                return RedirectResponse(
                    f"/app/wine/{int(wine_id)}/compliance?msg={_quote_msg(msg)}",
                    status_code=303,
                )

            if missing and force_publish and role != "admin":
                raise HTTPException(403, "Pubblicazione forzata consentita solo all'admin")

            _set_qr_status(cur, int(w["qr_item_id"]), "attiva")
            _set_labels_public(cur, int(wine_id), True)

            conn.commit()

    if missing and force_publish:
        return RedirectResponse(
            f"/app/wine/{int(wine_id)}?tab=export&msg=Pubblicato%20forzatamente%20con%20dati%20incompleti",
            status_code=303,
        )

    return RedirectResponse(
        f"/app/wine/{int(wine_id)}?tab=export&msg=Pubblicato",
        status_code=303,
    )


@router.post("/app/wine/{wine_id}/request-publish-override")
def request_publish_override(
    request: Request,
    wine_id: int,
    reason: str = Form(""),
):
    user = require_any_role(request, ("winery", "admin"))

    role = (user.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _load_wine(cur, int(wine_id))

            if role != "winery" or int(user["id"]) != int(w["owner_user_id"]):
                raise HTTPException(403, "Solo la cantina può richiedere lo sblocco admin")

            missing = _publication_missing_fields(cur, int(wine_id))

            if not missing:
                return RedirectResponse(
                    f"/app/wine/{int(wine_id)}?msg=I%20dati%20sono%20completi%3A%20puoi%20pubblicare%20normalmente",
                    status_code=303,
                )

            _upsert_override_request(
                cur,
                int(wine_id),
                int(w["winery_id"]),
                int(user["id"]),
                missing,
                reason,
            )

            conn.commit()

    return RedirectResponse(
        f"/app/wine/{int(wine_id)}/compliance?msg=Richiesta%20di%20sblocco%20inviata%20all%27admin",
        status_code=303,
    )


@router.post("/app/wine/{wine_id}/unpublish")
def unpublish_wine(request: Request, wine_id: int):
    user = require_any_role(request, ("winery", "studio", "admin"))

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _load_wine(cur, int(wine_id))

            if not _can_publish(user, w, cur):
                raise HTTPException(403, "Forbidden")

            _set_qr_status(cur, int(w["qr_item_id"]), "bozza")
            _set_labels_public(cur, int(wine_id), False)

            conn.commit()

    return RedirectResponse(
        f"/app/wine/{int(wine_id)}?tab=export&msg=In%20bozza",
        status_code=303,
    )
