"""Registration for businesses and professionals (QRFacile Link customers).

Light on purpose: email, password, business name, Terms and Privacy. Billing
data is asked only before the first purchase (/app/billing-profile).
"""
from __future__ import annotations

import time
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from passlib.hash import pbkdf2_sha256
from psycopg.rows import dict_row

from qrfacile_app.csrf_core import csrf_input
from qrfacile_app.db import pg
from qrfacile_app.legal_core import record_registration_acceptances
from qrfacile_app.modules.switches import is_enabled
from qrfacile_app.password_policy import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, new_password_error
from qrfacile_app.services.email_verification import create_verification
from qrfacile_app.ui_shell import esc, page, top_actions

router = APIRouter()


def _require_link() -> None:
    if not is_enabled("link"):
        raise HTTPException(404, "Pagina non trovata")


def _back(message: str) -> RedirectResponse:
    return RedirectResponse(f"/register-business?err={quote_plus(message)}", status_code=303)


def _input(name: str, label: str, type_: str, autocomplete: str, hint: str = "") -> str:
    extra = f' minlength="{MIN_PASSWORD_LENGTH}" maxlength="{MAX_PASSWORD_LENGTH}"' if type_ == "password" else ""
    help_html = f'<p class="muted" style="font-size:14px;margin:2px 0 0">{esc(hint)}</p>' if hint else ""
    return (
        f'<div><label for="rb-{name}">{esc(label)}</label>'
        f'<input class="input" id="rb-{name}" name="{name}" type="{type_}" autocomplete="{autocomplete}" required{extra}>'
        f"{help_html}</div>"
    )


@router.get("/register-business", response_class=HTMLResponse)
def register_business_get(request: Request, err: str = "", msg: str = ""):
    _require_link()
    body = f"""
    <section class="card" style="max-width:640px">
      <h2 class="h2">Crea il tuo account QRFacile Link</h2>
      <p class="p">Per negozi, ristoranti, professionisti, associazioni: un QR che porta a un link,
      a un PDF o a una mini-pagina. Puoi cambiare il contenuto quando vuoi, il QR stampato resta lo stesso.</p>
      <form method="post" action="/register-business" style="display:grid;gap:12px">
        {csrf_input(request)}
        {_input("business_name", "Nome dell'attività o tuo nome", "text", "organization")}
        {_input("email", "Email", "email", "email")}
        {_input("password", "Password", "password", "new-password", f"Almeno {MIN_PASSWORD_LENGTH} caratteri.")}
        {_input("password_confirm", "Conferma password", "password", "new-password")}
        <fieldset style="padding:16px;border:1px solid rgba(15,23,42,.14);border-radius:14px">
          <legend style="font-weight:800;padding:0 6px">Condizioni e privacy</legend>
          <div style="display:flex;gap:10px;align-items:flex-start">
            <input type="checkbox" id="rb-terms" name="terms_accepted" value="yes" required style="margin-top:4px">
            <label for="rb-terms">Ho letto e accetto i <a href="/terms" target="_blank" rel="noopener">Termini di servizio</a>.</label>
          </div>
          <div style="display:flex;gap:10px;align-items:flex-start;margin-top:10px">
            <input type="checkbox" id="rb-privacy" name="privacy_acknowledged" value="yes" required style="margin-top:4px">
            <label for="rb-privacy">Ho letto l'<a href="/privacy" target="_blank" rel="noopener">informativa privacy</a>. Non è un consenso marketing.</label>
          </div>
        </fieldset>
        <button class="btn btn-primary" type="submit">Crea account</button>
      </form>
      <p class="p" style="margin-top:12px">Hai una cantina? <a href="/register-winery">Registrati come cantina</a>.</p>
    </section>
    """
    return HTMLResponse(page(
        title="QRFACILE · Registrazione Link",
        subtitle="Account per aziende e professionisti",
        body_html=body,
        actions_html=top_actions(("/login", "Accedi")),
        msg=msg,
        err=err,
    ))


@router.post("/register-business")
def register_business_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    business_name: str = Form(...),
    terms_accepted: str = Form(""),
    privacy_acknowledged: str = Form(""),
):
    _require_link()
    email = (email or "").strip().lower()
    name = " ".join((business_name or "").split())[:120]
    if "@" not in email or len(email) > 254:
        return _back("Email non valida")
    policy_error = new_password_error(password or "")
    if policy_error:
        return _back(policy_error)
    if password != (password_confirm or ""):
        return _back("Le password non coincidono")
    if not name:
        return _back("Indica il nome dell'attività")
    if terms_accepted != "yes" or privacy_acknowledged != "yes":
        return _back("Devi accettare i Termini e confermare la Privacy")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO users (
                      email, pass_hash, role, display_name, created_at, email_verified, email_verification_required
                    )
                    VALUES (%s,%s,'business',%s,%s,0,TRUE)
                    RETURNING id
                    """,
                    (email, pbkdf2_sha256.hash(password), name, int(time.time())),
                )
                user_id = int(cur.fetchone()["id"])
            except Exception:
                conn.rollback()
                return _back("Email già registrata")
            record_registration_acceptances(cur, user_id=user_id, request=request)
        conn.commit()

    try:
        base_url = str(getattr(request.app.state, "app_base_url", "") or "").rstrip("/")
        if not base_url:
            base_url = f"{request.url.scheme}://{request.headers.get('host', '')}".rstrip("/")
        create_verification(user_id=user_id, base_url=base_url)
    except Exception:  # noqa: BLE001 - the account can resend from /verify-email-required
        pass
    return RedirectResponse("/login?created=1", status_code=303)
