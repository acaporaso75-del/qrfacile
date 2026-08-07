from __future__ import annotations

from urllib.parse import quote_plus

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.invitation_acceptance import (
    accept_invite_for_existing_studio,
    get_invite_by_token,
)
from qrfacile_app.ui_shell import esc, page_public

router = APIRouter(tags=["invitation-acceptance"])


def _same_origin(request: Request) -> None:
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin:
        return
    expected = f"{request.url.scheme}://{request.headers.get('host', '')}".rstrip("/")
    if origin != expected:
        raise HTTPException(403, "Origine richiesta non valida")


@router.get("/app/invite/studio/accept/{token}", response_class=HTMLResponse)
def invitation_landing(request: Request, token: str):
    invite = get_invite_by_token(token)
    body = f"""
    <section style='max-width:760px;margin:32px auto'>
      <div class='card'>
        <div class='h1'>Invito a collaborare</div>
        <div class='p'>La cantina <b>{esc(invite.get('winery_name') or '')}</b> ti invita a lavorare sulle proprie etichette in QRFACILE.</div>
        <div class='note' style='margin-top:14px'>
          Invito riservato a <b>{esc(invite.get('masked_email') or '')}</b>.<br>
          Lo studio può vedere o modificare secondo i permessi concessi, ma non può mai pubblicare.
        </div>
        <div class='row' style='margin-top:18px'>
          <form method='post' action='/app/invite/studio/accept/{esc(token)}'>
            <button class='btn btn-primary' type='submit'>Accetta con il mio account Studio</button>
          </form>
          <a class='btn' href='/register-studio?invite={esc(token)}'>Crea un nuovo account Studio</a>
          <a class='btn' href='/login?next={quote_plus(f"/app/invite/studio/accept/{token}")}'>Accedi</a>
        </div>
      </div>
    </section>
    """
    return HTMLResponse(page_public(
        title="QRFACILE · Invito studio",
        subtitle="Invito studio",
        body_html=body,
        actions_html='<a class="btn" href="/">Home</a>',
    ))


@router.post("/app/invite/studio/accept/{token}")
def invitation_accept(request: Request, token: str):
    _same_origin(request)
    user = require_any_role(request, ("studio",))
    result = accept_invite_for_existing_studio(
        token=token,
        studio_user_id=int(user.get("id") or 0),
        studio_email=str(user.get("email") or ""),
    )
    write_audit_event(
        action="studio_invitation_accepted",
        resource_type="studio_invite",
        resource_id=None,
        actor=user,
        request=request,
        metadata={
            "token_hash": result.get("token_hash"),
            "winery_id": result.get("winery_id"),
        },
    )
    return RedirectResponse(
        f"/studio/winery/{int(result['winery_id'])}?msg=Invito%20accettato",
        status_code=303,
    )
