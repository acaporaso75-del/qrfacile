from __future__ import annotations

from typing import Any, Mapping

from fastapi import HTTPException
from psycopg.rows import dict_row

from qrfacile_app.db import pg


PERMISSION_PROFILES = {
    "view": {"can_view": True, "can_edit": False, "can_media": False, "can_export": False},
    "graphic": {"can_view": True, "can_edit": True, "can_media": True, "can_export": True},
}


def _actor_role(actor: Mapping[str, Any]) -> str:
    return str(actor.get("role") or "").strip().lower()


def _actor_id(actor: Mapping[str, Any]) -> int:
    return int(actor.get("id") or actor.get("user_id") or 0)


def _load_label_for_owner(cur, label_id: int, actor: Mapping[str, Any]) -> dict[str, Any]:
    cur.execute(
        """
        SELECT wl.id AS label_id, wl.wine_id, wl.winery_id, w.owner_user_id
        FROM wine_labels wl
        JOIN wineries w ON w.id=wl.winery_id
        WHERE wl.id=%s
        LIMIT 1
        """,
        (int(label_id),),
    )
    label = cur.fetchone()
    if not label:
        raise HTTPException(404, "Etichetta non trovata")
    role = _actor_role(actor)
    if role != "admin" and not (role == "winery" and _actor_id(actor) == int(label.get("owner_user_id") or 0)):
        raise HTTPException(403, "Solo la cantina proprietaria può gestire questa etichetta")
    return dict(label)


def assign_studio_to_label(
    *,
    actor: Mapping[str, Any],
    label_id: int,
    studio_user_id: int,
    profile: str = "graphic",
) -> dict[str, Any]:
    profile = str(profile or "graphic").strip().lower()
    if profile not in PERMISSION_PROFILES:
        raise HTTPException(422, "Profilo permessi non valido")
    requested = PERMISSION_PROFILES[profile]

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label_for_owner(cur, label_id, actor)
            cur.execute(
                """
                SELECT can_view, can_edit, can_create
                FROM studio_clients
                WHERE winery_id=%s AND studio_user_id=%s AND can_view=TRUE
                LIMIT 1
                """,
                (int(label["winery_id"]), int(studio_user_id)),
            )
            general = cur.fetchone()
            if not general:
                raise HTTPException(422, "Lo studio non è collegato alla cantina")

            effective_view = bool(general.get("can_view") and requested["can_view"])
            effective_edit = bool(effective_view and general.get("can_edit") and requested["can_edit"])
            effective_media = bool(effective_edit and requested["can_media"])
            effective_export = bool(effective_view and requested["can_export"])

            cur.execute(
                """
                UPDATE label_collaborators
                SET active=FALSE, can_view=FALSE, can_edit=FALSE, can_media=FALSE,
                    can_export=FALSE, can_publish=FALSE, updated_at=now()
                WHERE wine_label_id=%s AND active=TRUE
                """,
                (int(label_id),),
            )
            cur.execute(
                """
                INSERT INTO label_collaborators (
                    wine_label_id, collaborator_user_id, role,
                    can_view, can_edit, can_media, can_export, can_publish,
                    commission_rate, active, created_at, updated_at
                ) VALUES (%s,%s,'studio',%s,%s,%s,%s,FALSE,0,TRUE,now(),now())
                ON CONFLICT (wine_label_id, collaborator_user_id) WHERE active=TRUE
                DO UPDATE SET role='studio', can_view=EXCLUDED.can_view,
                    can_edit=EXCLUDED.can_edit, can_media=EXCLUDED.can_media,
                    can_export=EXCLUDED.can_export, can_publish=FALSE,
                    commission_rate=0, active=TRUE, updated_at=now()
                RETURNING id, wine_label_id, collaborator_user_id, can_view,
                          can_edit, can_media, can_export, can_publish, active
                """,
                (int(label_id), int(studio_user_id), effective_view, effective_edit, effective_media, effective_export),
            )
            row = dict(cur.fetchone())
        conn.commit()
    return {"label": label, "collaboration": row, "profile": profile}


def clear_label_collaboration(*, actor: Mapping[str, Any], label_id: int) -> dict[str, Any]:
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label_for_owner(cur, label_id, actor)
            cur.execute(
                """
                UPDATE label_collaborators
                SET active=FALSE, can_view=FALSE, can_edit=FALSE, can_media=FALSE,
                    can_export=FALSE, can_publish=FALSE, updated_at=now()
                WHERE wine_label_id=%s AND active=TRUE
                """,
                (int(label_id),),
            )
            changed = cur.rowcount
        conn.commit()
    return {"label": label, "deactivated": int(changed or 0)}


def update_studio_connection_profile(
    *, actor: Mapping[str, Any], studio_client_id: int, profile: str
) -> dict[str, Any]:
    profile = str(profile or "").strip().lower()
    profiles = {
        "view": (True, False, False),
        "graphic": (True, True, False),
        "full": (True, True, True),
    }
    if profile not in profiles:
        raise HTTPException(422, "Profilo non valido")
    can_view, can_edit, can_create = profiles[profile]
    role, uid = _actor_role(actor), _actor_id(actor)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT sc.id, sc.winery_id, sc.studio_user_id, w.owner_user_id
                FROM studio_clients sc JOIN wineries w ON w.id=sc.winery_id
                WHERE sc.id=%s LIMIT 1
                """,
                (int(studio_client_id),),
            )
            link = cur.fetchone()
            if not link:
                raise HTTPException(404, "Collegamento non trovato")
            if role != "admin" and not (role == "winery" and uid == int(link.get("owner_user_id") or 0)):
                raise HTTPException(403, "Non autorizzato")
            cur.execute(
                """UPDATE studio_clients SET can_view=%s, can_edit=%s, can_create=%s
                   WHERE id=%s RETURNING id, winery_id, studio_user_id, can_view, can_edit, can_create""",
                (can_view, can_edit, can_create, int(studio_client_id)),
            )
            updated = dict(cur.fetchone())
        conn.commit()
    return updated


def revoke_studio_connection(*, actor: Mapping[str, Any], studio_client_id: int) -> dict[str, Any]:
    role, uid = _actor_role(actor), _actor_id(actor)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT sc.id, sc.winery_id, sc.studio_user_id, w.owner_user_id
                FROM studio_clients sc JOIN wineries w ON w.id=sc.winery_id
                WHERE sc.id=%s LIMIT 1
                """,
                (int(studio_client_id),),
            )
            link = cur.fetchone()
            if not link:
                raise HTTPException(404, "Collegamento non trovato")
            if role != "admin" and not (role == "winery" and uid == int(link.get("owner_user_id") or 0)):
                raise HTTPException(403, "Non autorizzato")
            cur.execute(
                """
                UPDATE label_collaborators lc
                SET active=FALSE, can_view=FALSE, can_edit=FALSE, can_media=FALSE,
                    can_export=FALSE, can_publish=FALSE, updated_at=now()
                FROM wine_labels wl
                WHERE lc.wine_label_id=wl.id AND wl.winery_id=%s
                  AND lc.collaborator_user_id=%s AND lc.active=TRUE
                """,
                (int(link["winery_id"]), int(link["studio_user_id"])),
            )
            labels_revoked = cur.rowcount
            cur.execute("DELETE FROM studio_clients WHERE id=%s", (int(studio_client_id),))
        conn.commit()
    return {"winery_id": int(link["winery_id"]), "studio_user_id": int(link["studio_user_id"]), "labels_revoked": int(labels_revoked or 0)}
