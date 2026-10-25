from __future__ import annotations

from urllib.parse import quote_plus

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.auth_core import get_current_user
from qrfacile_app.csrf_core import csrf_input, require_csrf_or_same_origin
from qrfacile_app.services.email_verification import create_verification, verify_email
from qrfacile_app.ui_shell import esc, page_public

router = APIRouter(tags=["email-verification"])


def _base_url(request: Request) -> str:
    configured = str(getattr(request.app.state, "app_base_url", "") or "").rstrip("/")
    return configured or f"{request.url.scheme}://{request.headers.get('host', '')}".rstrip("/")


@router.get("/verify-email-required", response_class=HTMLResponse)
def verification_required_page(request: Request, next: str = "/app/start"):
    user = get_current_user(request)
    if bool(user.get("email_verified")) or not bool(user.get("email_verification_required")):
        target = next if next.startswith("/") and not next.startswith("//") else "/app/start"
        return RedirectResponse(target, status_code=303)
    body = f"""
    <div class='card'>
      <div class='h1'>Verifica il tuo indirizzo email</div>
      <div class='p'>Prima di usare le funzioni riservate, apri il collegamento inviato a <b>{esc(user.get('email',''))}</b>.</div>
      <form method='post' action='/api/me/email-verification/resend' style='margin-top:16px'>
        {csrf_input(request)}
        <button class='btn btn-primary' type='submit'>Invia di nuovo l'email</button>
      </form>
      <div class='row' style='margin-top:12px'><a class='btn' href='/logout'>Esci</a></div>
    </div>
    """
    return HTMLResponse(page_public(title="QRFACILE · Verifica email richiesta", subtitle="Verifica email", body_html=body))


@router.get("/verify-email/{token}", response_class=HTMLResponse)
def verify_email_page(request: Request, token: str):
    try:
        result = verify_email(token)
        body = "<div class='card'><div class='h1'>Email verificata</div><div class='p'>Il tuo indirizzo è stato confermato. Ora puoi accedere a QRFACILE.</div><div class='row' style='margin-top:14px'><a class='btn btn-primary' href='/login'>Accedi</a></div></div>"
        write_audit_event(action="email_verified", resource_type="user", resource_id=result["user_id"], request=request)
        return HTMLResponse(page_public(title="QRFACILE · Email verificata", subtitle="Verifica email", body_html=body))
    except HTTPException as exc:
        body = f"<div class='card'><div class='h1'>Verifica non riuscita</div><div class='p'>{esc(str(exc.detail))}</div><div class='row' style='margin-top:14px'><a class='btn' href='/login'>Torna al login</a></div></div>"
        return HTMLResponse(page_public(title="QRFACILE · Verifica email", subtitle="Verifica email", body_html=body), status_code=exc.status_code)


@router.post("/api/me/email-verification/resend")
def resend_verification(request: Request, csrf_token: str = Form("")):
    require_csrf_or_same_origin(request, csrf_token)
    user = get_current_user(request)
    result = create_verification(user_id=int(user["id"]), base_url=_base_url(request))
    write_audit_event(
        action="email_verification_requested",
        resource_type="user",
        resource_id=int(user["id"]),
        actor=user,
        request=request,
        metadata={"email_sent": bool(result.get("email_sent")), "already_verified": bool(result.get("already_verified"))},
    )
    msg = "Email di verifica inviata" if result.get("email_sent") else ("Email già verificata" if result.get("already_verified") else "Invio email non riuscito")
    return RedirectResponse(f"/app/start?msg={quote_plus(msg)}", status_code=303)
