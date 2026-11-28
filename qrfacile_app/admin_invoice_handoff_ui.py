"""Admin view of paid orders handed over to Danea Easyfatt for invoicing."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import csrf_input, require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.services.invoice_handoff import (
    InvoiceHandoffError,
    build_easyfatt_xml,
    invoice_data,
    load_recipients,
    send_invoice_handoff,
)
from qrfacile_app.ui_shell import esc, page, pill, top_actions


router = APIRouter()

_ERRORS = {
    "recipients_not_configured": "Destinatari fatturazione non configurati",
    "fiscal_snapshot_missing": "Ordine storico senza dati fiscali congelati: fattura manuale",
    "amounts_inconsistent": "Importi incoerenti: verificare prima di fatturare",
    "paid_at_missing": "Data di pagamento assente",
    "order_not_paid": "Ordine non pagato",
    "smtp_not_configured": "SMTP non configurato",
    "smtp_recipient_refused": "Destinatario rifiutato dal server di posta",
    "smtp_delivery_failed": "Invio e-mail non riuscito",
}


def _status(order: dict) -> str:
    if order.get("invoice_handoff_sent_at"):
        return pill("Inviato a fatturazione", "green")
    if order.get("invoice_handoff_last_error"):
        return pill("Da gestire", "warn")
    return pill("Non inviato", "muted")


@router.get("/admin/invoices", response_class=HTMLResponse)
def invoice_handoff_page(request: Request, msg: str = "", err: str = ""):
    user = require_any_role(request, ("admin",))
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # to_jsonb keeps the page readable before the hand-off migration.
            cur.execute(
                """
                SELECT to_jsonb(o) AS o
                FROM orders o
                WHERE o.status='paid'
                ORDER BY o.paid_at DESC NULLS LAST, o.id DESC
                LIMIT 100
                """
            )
            orders = [row["o"] for row in (cur.fetchall() or [])]

    token = csrf_input(request)
    cards = []
    for order in orders:
        order_id = int(order["id"])
        try:
            data = invoice_data(order)
        except InvoiceHandoffError as exc:
            data = None
            reason = _ERRORS.get(str(exc), str(exc))
        customer = (data or {}).get("customer") or {}
        error = order.get("invoice_handoff_last_error") or ""
        details = (
            f"<p>{esc(customer.get('name') or '-')} · P.IVA {esc(customer.get('vat') or '-')} · "
            f"SDI {esc(customer.get('sdi') or '-')} · totale € {int(order.get('amount_cents') or 0) / 100:.2f}</p>"
            if data
            else f"<p class='muted'>{esc(reason)}</p>"
        )
        download = (
            f'<a class="btn" href="/admin/invoices/{order_id}/easyfatt.DefXml">Scarica file Danea</a>'
            if data
            else ""
        )
        resend = (
            f"""
            <form method="post" action="/admin/invoices/{order_id}/send" style="display:inline">
              {token}
              <button class="btn" type="submit">{'Reinvia' if order.get('invoice_handoff_sent_at') else 'Invia'} a fatturazione</button>
            </form>
            """
            if data
            else ""
        )
        cards.append(
            f"""
            <article class="card" style="margin-top:12px">
              <div class="row" style="justify-content:space-between">
                <strong>Ordine {order_id} · {esc(order.get('pack') or '-')} · {esc(order.get('payment_environment') or 'unknown')}</strong>
                {_status(order)}
              </div>
              {details}
              {f"<p class='muted'>Ultimo errore: {esc(_ERRORS.get(error, error))}</p>" if error else ''}
              <div class="row" style="gap:8px">{download}{resend}</div>
            </article>
            """
        )

    configured = load_recipients() is not None
    note = (
        "<div class='note' role='note'>Ogni ordine pagato invia una e-mail con i dati di fatturazione "
        "e il file Easyfatt-Xml da importare in Danea (Utilità &gt; Importa documenti Easyfatt-Xml).</div>"
        if configured
        else "<div class='note note-err' role='alert'>Destinatari non configurati: impostare "
        "QRFACILE_INVOICE_TO (e facoltativo QRFACILE_INVOICE_CC) nell'ambiente del servizio.</div>"
    )
    body = note + ("".join(cards) or "<div class='card'><p>Nessun ordine pagato.</p></div>")
    return HTMLResponse(page(
        title="QRFACILE · Fatturazione",
        subtitle="Ordini pagati da fatturare in Danea",
        body_html=body,
        actions_html=top_actions(("/admin", "Admin"), ("/admin/paypal-webhooks", "Eventi PayPal")),
        msg=msg,
        err=err,
        role="admin",
        user_email=user.get("email", ""),
        credits=None,
    ))


@router.get("/admin/invoices/{order_id}/easyfatt.DefXml")
def download_easyfatt(request: Request, order_id: int):
    require_any_role(request, ("admin",))
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM orders WHERE id=%s", (int(order_id),))
            order = cur.fetchone()
    if not order:
        raise HTTPException(404, "Ordine non trovato")
    try:
        data = invoice_data(order)
    except InvoiceHandoffError as exc:
        raise HTTPException(409, _ERRORS.get(str(exc), "Ordine non fatturabile automaticamente")) from exc
    return Response(
        build_easyfatt_xml(data),
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="qrfacile-ordine-{int(order_id)}.DefXml"',
            "Cache-Control": "no-store",
        },
    )


@router.post("/admin/invoices/{order_id}/send")
def resend_invoice_handoff(request: Request, order_id: int):
    require_csrf_or_same_origin(request)
    require_any_role(request, ("admin",))
    result = send_invoice_handoff(int(order_id), force=True)
    if result == "sent":
        return RedirectResponse("/admin/invoices?msg=Inviato%20a%20fatturazione", status_code=303)
    message = _ERRORS.get(result, "Invio non riuscito")
    return RedirectResponse(f"/admin/invoices?err={message.replace(' ', '%20')}", status_code=303)
