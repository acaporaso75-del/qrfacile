"""Billing profile page: who receives the invoice for Link purchases."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import csrf_input, require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.pricing_config import EU_VAT_RATES
from qrfacile_app.services.billing_profile import (
    load_billing_profile,
    normalize_billing_profile,
    save_billing_profile,
    vies_check,
)
from qrfacile_app.ui_shell import esc, page

router = APIRouter()
ROLES = ("admin", "winery", "studio", "collaborator", "business")
TYPE_LABELS = {"company": "Azienda o professionista con Partita IVA", "private": "Privato", "association": "Associazione o ente"}


def _safe_next(value: str) -> str:
    value = (value or "").strip()
    if not value.startswith("/") or value.startswith("//") or len(value) > 200:
        return ""
    # Browsers read "/\host" as "//host"; control characters split headers.
    if "\\" in value or any(ord(ch) < 32 for ch in value):
        return ""
    return value


def _field(name: str, label: str, value: str, hint: str = "", **attrs: str) -> str:
    extra = " ".join(f'{k}="{esc(v)}"' for k, v in attrs.items())
    help_html = f'<p class="muted" style="font-size:14px;margin:2px 0 0">{esc(hint)}</p>' if hint else ""
    return (
        f'<div><label for="bp-{name}">{esc(label)}</label>'
        f'<input id="bp-{name}" class="input" name="{name}" value="{esc(value or "")}" {extra}>{help_html}</div>'
    )


@router.get("/app/billing-profile", response_class=HTMLResponse)
def billing_profile_get(request: Request, msg: str = "", err: str = "", next: str = ""):
    user = require_any_role(request, ROLES)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            profile = load_billing_profile(cur, int(user["id"])) or {}
    kind = profile.get("customer_type") or "company"
    types = "".join(
        f'<option value="{k}"{" selected" if kind == k else ""}>{esc(v)}</option>' for k, v in TYPE_LABELS.items()
    )
    country = profile.get("country") or "IT"
    countries = ["IT", *sorted(c for c in EU_VAT_RATES if c != "IT")]
    if country not in countries:
        countries.append(country)
    options = "".join(f'<option value="{c}"{" selected" if c == country else ""}>{c}</option>' for c in countries)
    vies = ""
    if profile.get("country") and profile.get("country") != "IT" and profile.get("vat_number"):
        state = {True: "verificata su VIES", False: "non risulta valida su VIES"}.get(profile.get("vies_valid"), "non ancora verificata")
        vies = f'<p class="note" role="note">Partita IVA UE {esc(state)}.</p>'
    body = f"""
    <section class="card">
      <h2 class="h2">Dati per la fattura</h2>
      <p class="p">Servono una volta sola. Il prezzo è IVA inclusa; ricevi la fattura elettronica dopo il pagamento.</p>
      {vies}
      <form method="post" action="/app/billing-profile" style="display:grid;gap:12px">
        {csrf_input(request)}
        <input type="hidden" name="next" value="{esc(_safe_next(next))}">
        <div><label for="bp-customer_type">Chi riceve la fattura</label>
          <select id="bp-customer_type" name="customer_type">{types}</select></div>
        <div><label for="bp-country">Paese</label>
          <select id="bp-country" name="country">{options}</select>
          <p class="muted" style="font-size:14px;margin:2px 0 0">Per altri Paesi scrivi a info@qrfacile.it.</p></div>
        {_field("name", "Nome e cognome o ragione sociale", profile.get("name"), autocomplete="organization")}
        {_field("vat_number", "Partita IVA (aziende)", profile.get("vat_number"), "Per aziende UE fuori dall'Italia viene verificata su VIES.")}
        {_field("fiscal_code", "Codice fiscale (privati e associazioni)", profile.get("fiscal_code"))}
        {_field("address", "Indirizzo", profile.get("address"), autocomplete="street-address")}
        {_field("postcode", "CAP", profile.get("postcode"), autocomplete="postal-code")}
        {_field("city", "Città", profile.get("city"), autocomplete="address-level2")}
        {_field("province", "Provincia (sigla)", profile.get("province"), maxlength="2")}
        {_field("sdi", "Codice destinatario SDI (aziende italiane)", profile.get("sdi"), "7 caratteri. In alternativa indica la PEC.", maxlength="7")}
        {_field("pec", "PEC", profile.get("pec"), type="email")}
        {_field("invoice_email", "Email per la copia della fattura", profile.get("invoice_email"), type="email", autocomplete="email")}
        <button class="btn btn-primary" type="submit">Salva dati fattura</button>
      </form>
    </section>
    """
    return HTMLResponse(page(
        title="QRFACILE · Dati fattura",
        subtitle="Chi riceve la fattura degli acquisti",
        body_html=body,
        msg=msg,
        err=err,
        role=user.get("role", ""),
        user_email=user.get("email", ""),
        credits=None,
    ))


@router.post("/app/billing-profile")
async def billing_profile_post(request: Request):
    require_csrf_or_same_origin(request)
    user = require_any_role(request, ROLES)
    form = await request.form()
    data = {key: str(form.get(key) or "") for key in form.keys()} if hasattr(form, "keys") else dict(form)
    next_url = _safe_next(data.get("next", ""))
    back = f"/app/billing-profile?next={quote(next_url)}&" if next_url else "/app/billing-profile?"
    try:
        profile = normalize_billing_profile(data)
    except HTTPException as exc:
        return RedirectResponse(f"{back}err={quote(str(exc.detail))}", status_code=303)
    profile["vies_valid"] = None
    if profile["country"] != "IT" and profile["country"] in EU_VAT_RATES and profile.get("vat_number"):
        profile["vies_valid"] = vies_check(profile["country"], profile["vat_number"])
    with pg() as conn:
        with conn.cursor() as cur:
            save_billing_profile(cur, int(user["id"]), profile)
        conn.commit()
    if next_url:
        return RedirectResponse(next_url, status_code=303)
    return RedirectResponse(f"/app/billing-profile?msg={quote('Dati fattura salvati')}", status_code=303)
