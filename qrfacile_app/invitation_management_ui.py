from __future__ import annotations

from urllib.parse import quote_plus

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.services.invitation_management import create_invite, resend_invite, revoke_invite

router = APIRouter(tags=["invitation-management"])


def _winery_id(user: dict) -> int:
    role = str(user.get("role") or "").lower()
    if role == "admin":
        raise HTTPException(422, "L'amministratore deve operare dal contesto di una cantina")
    with pg() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM wineries WHERE owner_user_id=%s LIMIT 1", (int(user["id"]),))
            row = cur.fetchone()
    if not row:
        raise HTTPException(403, "Cantina non trovata")
    return int(row[0])


def _base_url(request: Request) -> str:
    configured = str(getattr(request.app.state, "app_base_url", "") or "").rstrip("/")
    if configured:
        return configured
    return f"{request.url.scheme}://{request.headers.get('host', '')}".rstrip("/")


@router.post("/app/settings/studios/invite")
def secure_create_studio_invite(
    request: Request,
    studio_email: str = Form(...),
    preset: str = Form("graphic"),
):
    require_csrf_or_same_origin(request)
    user = require_any_role(request, ("winery",))
    winery_id = _winery_id(user)
    result = create_invite(
        winery_id=winery_id,
        actor_user_id=int(user["id"]),
        studio_email=studio_email,
        preset=preset,
        base_url=_base_url(request),
    )
    write_audit_event(
        action="studio_invitation_created",
        resource_type="studio_invite",
        resource_id=result["token_hash"],
        actor=user,
        request=request,
        metadata={
            "winery_id": winery_id,
            "studio_email": result["studio_email"],
            "email_sent": result["email_sent"],
            "delivery_status": "sent" if result["email_sent"] else "failed",
        },
    )
    msg = "Invito inviato allo studio" if result["email_sent"] else "Invito creato; invio email non riuscito"
    return RedirectResponse(f"/app/winery/settings?msg={quote_plus(msg)}", status_code=303)


@router.post("/app/settings/studios/invites/{token_hash}/revoke")
def secure_revoke_studio_invite(request: Request, token_hash: str):
    require_csrf_or_same_origin(request)
    user = require_any_role(request, ("winery",))
    winery_id = _winery_id(user)
    result = revoke_invite(winery_id=winery_id, token_hash=token_hash, actor_user_id=int(user["id"]))
    write_audit_event(
        action="studio_invitation_revoked",
        resource_type="studio_invite",
        resource_id=token_hash,
        actor=user,
        request=request,
        metadata={"winery_id": winery_id, "studio_email": result.get("studio_email")},
    )
    return RedirectResponse("/app/winery/settings?msg=Invito%20revocato", status_code=303)


@router.post("/app/settings/studios/invites/{token_hash}/resend")
def secure_resend_studio_invite(request: Request, token_hash: str):
    require_csrf_or_same_origin(request)
    user = require_any_role(request, ("winery",))
    winery_id = _winery_id(user)
    result = resend_invite(winery_id=winery_id, token_hash=token_hash, base_url=_base_url(request))
    write_audit_event(
        action="studio_invitation_resent",
        resource_type="studio_invite",
        resource_id=token_hash,
        actor=user,
        request=request,
        metadata={"winery_id": winery_id, "email_sent": result["email_sent"]},
    )
    msg = "Invito reinviato" if result["email_sent"] else "Reinvio non riuscito"
    return RedirectResponse(f"/app/winery/settings?msg={quote_plus(msg)}", status_code=303)
