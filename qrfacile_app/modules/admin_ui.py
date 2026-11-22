"""Admin page to switch vertical modules and their sales on or off."""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import csrf_input, require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.modules.switches import set_enabled
from qrfacile_app.ui_shell import esc, page, pill, top_actions

router = APIRouter()

SWITCH_LABELS = {
    "link": ("QRFacile Link", "Mostra il modulo ai clienti: area Link, registrazione Azienda, pagina /link."),
    "link_sales_it": ("Vendite Link Italia", "Acquisto online dei pacchetti Link con profilo di fatturazione e fattura Danea."),
    "link_sales_foreign": ("Vendite estero", "Acquisto da UE ed extra-UE. Accendere solo dopo l'ok del commercialista sulla tabella IVA."),
    "link_oss_threshold_exceeded": ("Soglia OSS superata", "Accendere quando le vendite a privati UE superano 10.000 € l'anno: si applica l'IVA del paese del cliente."),
}


def _load_switches() -> list[dict]:
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT s.key, s.enabled, s.updated_at, u.email AS updated_by_email
                FROM module_switches s LEFT JOIN users u ON u.id = s.updated_by
                ORDER BY s.key
                """
            )
            return cur.fetchall() or []


@router.get("/admin/modules", response_class=HTMLResponse)
def modules_page(request: Request, msg: str = "", err: str = ""):
    user = require_any_role(request, ("admin",))
    token = csrf_input(request)
    cards = []
    for row in _load_switches():
        key = str(row["key"])
        label, help_text = SWITCH_LABELS.get(key, (key, ""))
        enabled = bool(row.get("enabled"))
        next_value = "off" if enabled else "on"
        changed = f"Ultima modifica: {esc(str(row.get('updated_at') or '-'))} · {esc(row.get('updated_by_email') or '-')}"
        cards.append(
            f"""
            <article class="card" style="margin-top:12px">
              <div class="row" style="justify-content:space-between">
                <strong>{esc(label)}</strong>
                {pill("Acceso", "green") if enabled else pill("Spento", "muted")}
              </div>
              <p class="p">{esc(help_text)}</p>
              <p class="muted">{changed}</p>
              <form method="post" action="/admin/modules/{esc(key)}">
                {token}
                <input type="hidden" name="enabled" value="{next_value}">
                <button class="btn{' btn-primary' if not enabled else ''}" type="submit">{'Spegni' if enabled else 'Accendi'}</button>
              </form>
            </article>
            """
        )
    body = (
        "<div class='note' role='note'>Gli interruttori hanno effetto entro 10 secondi, senza riavvio. "
        "Un modulo spento non è visibile ai clienti, ma i QR già stampati continuano a funzionare.</div>"
        + ("".join(cards) or "<div class='card'><p>Nessun interruttore: applicare la migrazione dei moduli.</p></div>")
    )
    return HTMLResponse(page(
        title="QRFACILE · Moduli",
        subtitle="Accensione dei moduli verticali",
        body_html=body,
        actions_html=top_actions(("/admin", "Admin")),
        msg=msg,
        err=err,
        role="admin",
        user_email=user.get("email", ""),
        credits=None,
    ))


@router.post("/admin/modules/{key}")
def toggle_module(request: Request, key: str, enabled: str = Form(...)):
    require_csrf_or_same_origin(request)
    user = require_any_role(request, ("admin",))
    try:
        set_enabled(key, enabled == "on", user_id=int(user["id"]))
    except KeyError as exc:
        raise HTTPException(404, "Interruttore sconosciuto") from exc
    return RedirectResponse("/admin/modules?msg=Interruttore%20aggiornato", status_code=303)
