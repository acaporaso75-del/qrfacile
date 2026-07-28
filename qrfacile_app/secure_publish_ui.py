from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.publish_routes import (
    _can_publish,
    _load_wine,
    _publication_missing_fields,
    _quote_msg,
    _set_labels_public,
    _set_qr_status,
    _upsert_override_request,
)
from qrfacile_app.services.wine_compliance_replay import create_and_persist_replay
from qrfacile_app.wine_compliance_engine_ui import _load_payload

router = APIRouter(tags=["secure-publishing"])


@router.post("/app/wine/{wine_id}/publish")
def secure_publish_wine(
    request: Request,
    wine_id: int,
    force: str = Form(""),
    csrf_token: str = Form(""),
):
    require_csrf_or_same_origin(request, csrf_token)
    user = require_any_role(request, ("winery", "admin"))
    role = str(user.get("role") or "").lower()
    force_publish = (force or "").strip() == "1"

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            wine = _load_wine(cur, int(wine_id))
            if not _can_publish(user, wine, cur):
                raise HTTPException(403, "Pubblicazione non autorizzata")
            missing = _publication_missing_fields(cur, int(wine_id))
            if missing and not force_publish:
                msg = "Pubblicazione bloccata. Mancano dati obbligatori: " + ", ".join(missing)
                return RedirectResponse(
                    f"/app/wine/{int(wine_id)}/compliance?msg={_quote_msg(msg)}",
                    status_code=303,
                )
            if missing and force_publish and role != "admin":
                raise HTTPException(403, "Pubblicazione forzata consentita solo all'amministratore")
            _set_qr_status(cur, int(wine["qr_item_id"]), "attiva")
            _set_labels_public(cur, int(wine_id), True)
        conn.commit()

    payload = _load_payload(int(wine_id), user)
    replay = create_and_persist_replay(
        payload,
        actor_user_id=int(user.get("id") or 0) or None,
        reason="forced_publication" if force_publish else "publication",
    )
    write_audit_event(
        action="wine_published_forced" if force_publish else "wine_published",
        resource_type="wine",
        resource_id=wine_id,
        actor=user,
        request=request,
        metadata={
            "missing_fields": missing,
            "replay_id": str(replay.get("replay_id") or ""),
            "content_hash": str(replay.get("content_hash") or ""),
        },
    )
    suffix = "Pubblicato%20forzatamente" if force_publish else "Pubblicato"
    return RedirectResponse(f"/app/wine/{int(wine_id)}?tab=export&msg={suffix}", status_code=303)


@router.post("/app/wine/{wine_id}/unpublish")
def secure_unpublish_wine(
    request: Request,
    wine_id: int,
    csrf_token: str = Form(""),
):
    require_csrf_or_same_origin(request, csrf_token)
    user = require_any_role(request, ("winery", "admin"))
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            wine = _load_wine(cur, int(wine_id))
            if not _can_publish(user, wine, cur):
                raise HTTPException(403, "Operazione non autorizzata")
            _set_qr_status(cur, int(wine["qr_item_id"]), "bozza")
            _set_labels_public(cur, int(wine_id), False)
        conn.commit()
    write_audit_event(
        action="wine_unpublished",
        resource_type="wine",
        resource_id=wine_id,
        actor=user,
        request=request,
    )
    return RedirectResponse(f"/app/wine/{int(wine_id)}?tab=export&msg=In%20bozza", status_code=303)


@router.post("/app/wine/{wine_id}/request-publish-override")
def secure_request_publish_override(
    request: Request,
    wine_id: int,
    reason: str = Form(""),
    csrf_token: str = Form(""),
):
    require_csrf_or_same_origin(request, csrf_token)
    user = require_any_role(request, ("winery",))
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            wine = _load_wine(cur, int(wine_id))
            if int(user["id"]) != int(wine["owner_user_id"]):
                raise HTTPException(403, "Solo la cantina proprietaria può richiedere lo sblocco")
            missing = _publication_missing_fields(cur, int(wine_id))
            if not missing:
                return RedirectResponse(
                    f"/app/wine/{int(wine_id)}?msg=Dati%20completi%3A%20pubblicazione%20normale%20disponibile",
                    status_code=303,
                )
            request_id = _upsert_override_request(
                cur,
                int(wine_id),
                int(wine["winery_id"]),
                int(user["id"]),
                missing,
                reason,
            )
        conn.commit()
    write_audit_event(
        action="publish_override_requested",
        resource_type="publish_override_request",
        resource_id=request_id,
        actor=user,
        request=request,
        metadata={"wine_id": wine_id, "missing_fields": missing, "reason": reason[:500]},
    )
    return RedirectResponse(
        f"/app/wine/{int(wine_id)}/compliance?msg=Richiesta%20di%20sblocco%20inviata",
        status_code=303,
    )
