"""Hand a paid order over to the internal invoicing team (Danea Easyfatt).

QRFACILE does not issue invoices. When an order is paid, the billing office
receives one e-mail with the customer's fiscal data, the amounts and an
Easyfatt-Xml file (.DefXml) that Easyfatt imports as an invoice through
"Utilità > Importa documenti Easyfatt-Xml".

Recipients come only from the runtime environment:
- QRFACILE_INVOICE_TO: required, one address;
- QRFACILE_INVOICE_CC: optional, comma separated.

The hand-off never blocks or reverses a payment: failures are recorded on the
order and the file stays downloadable from the admin area.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from email.message import EmailMessage
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.services.transactional_email import send_email_message

ROME = ZoneInfo("Europe/Rome")
EMAIL_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")

# Issuer shown in the Easyfatt header; matches the legal footer of the site.
ISSUER = {
    "Name": "Enolab S.r.l.",
    "Address": "Via Campoli-Friuni snc",
    "City": "Campoli del Monte Taburno",
    "Province": "BN",
    "Country": "Italia",
    "FiscalCode": "01413300623",
    "VatCode": "01413300623",
}

# Easyfatt-Xml document type for a sales invoice.
EASYFATT_INVOICE = "I"


class InvoiceHandoffError(RuntimeError):
    """The order cannot be handed over; the message is safe to store."""


def load_recipients(environ: Mapping[str, str] | None = None) -> tuple[str, list[str]] | None:
    source = os.environ if environ is None else environ
    to = (source.get("QRFACILE_INVOICE_TO") or "").strip()
    if not EMAIL_RE.match(to):
        return None
    cc = [item.strip() for item in (source.get("QRFACILE_INVOICE_CC") or "").split(",") if item.strip()]
    if any(not EMAIL_RE.match(item) for item in cc):
        return None
    return to, [item for item in cc if item.lower() != to.lower()]


def _cents(value: Any) -> int:
    return int(value or 0)


def _money(cents: int) -> str:
    return str((Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _euro(cents: int) -> str:
    return "€ " + _money(cents).replace(".", ",")


def invoice_data(order: Mapping[str, Any]) -> dict[str, Any]:
    """Return the invoice facts frozen in the order at checkout time.

    Only orders with a commercial snapshot (the current annual Wine offer)
    carry a validated Italian fiscal profile and an explicit net/VAT split.
    """
    if str(order.get("status") or "").lower() != "paid":
        raise InvoiceHandoffError("order_not_paid")
    snapshot = order.get("commercial_snapshot") or {}
    customer = snapshot.get("customer") or {}
    if not snapshot or not customer:
        raise InvoiceHandoffError("fiscal_snapshot_missing")

    net = _cents(snapshot.get("net_cents"))
    vat = _cents(snapshot.get("vat_cents"))
    gross = _cents(snapshot.get("gross_cents"))
    if net <= 0 or vat < 0 or net + vat != gross or gross != _cents(order.get("amount_cents")):
        raise InvoiceHandoffError("amounts_inconsistent")

    paid_at = order.get("paid_at")
    if not paid_at:
        raise InvoiceHandoffError("paid_at_missing")
    paid = datetime.fromtimestamp(int(paid_at), tz=timezone.utc).astimezone(ROME)
    units = int(snapshot.get("wine_credits") or 0)
    name = str(snapshot.get("name") or order.get("pack") or "").strip()

    return {
        "order_id": int(order["id"]),
        "environment": str(order.get("payment_environment") or "unknown"),
        "paypal_capture_id": str(order.get("paypal_capture_id") or ""),
        "paid_date": paid.date().isoformat(),
        "paid_label": paid.strftime("%d/%m/%Y %H:%M"),
        "customer": {
            "name": str(customer.get("name") or ""),
            "vat": str(customer.get("vat") or ""),
            "sdi": str(customer.get("sdi") or ""),
            "pec": str(customer.get("pec") or ""),
            "address": str(customer.get("billing_address") or ""),
            "postcode": str(customer.get("billing_cap") or ""),
            "city": str(customer.get("city") or ""),
            "province": str(customer.get("province") or ""),
            "country": str(customer.get("billing_country") or "IT"),
        },
        "description": (
            f"QRFACILE Wine - pacchetto {name}: {units} unità QR vino "
            f"utilizzabili entro 12 mesi (ordine n. {int(order['id'])})"
        ),
        "net_cents": net,
        "vat_cents": vat,
        "gross_cents": gross,
        "vat_rate": int(snapshot.get("vat_rate") or 22),
    }


def _child(parent: ET.Element, tag: str, text: Any = "") -> ET.Element:
    element = ET.SubElement(parent, tag)
    element.text = "" if text is None else str(text)
    return element


def build_easyfatt_xml(data: Mapping[str, Any]) -> bytes:
    """Easyfatt-Xml with one invoice, net prices and the VAT rate of the order.

    The document number is left to Easyfatt, which assigns the next number of
    its own invoice numbering on import.
    """
    customer = data["customer"]
    root = ET.Element(
        "EasyfattDocuments",
        {
            "AppVersion": "2",
            "Creator": "QRFACILE",
            "CreatorUrl": "https://www.qrfacile.it",
        },
    )
    company = ET.SubElement(root, "Company")
    for tag, value in ISSUER.items():
        _child(company, tag, value)

    documents = ET.SubElement(root, "Documents")
    document = ET.SubElement(documents, "Document")
    _child(document, "DocumentType", EASYFATT_INVOICE)
    _child(document, "Date", data["paid_date"])
    _child(document, "CustomerName", customer["name"])
    _child(document, "CustomerAddress", customer["address"])
    _child(document, "CustomerPostcode", customer["postcode"])
    _child(document, "CustomerCity", customer["city"])
    _child(document, "CustomerProvince", customer["province"])
    _child(document, "CustomerCountry", "Italia" if customer["country"] == "IT" else customer["country"])
    _child(document, "CustomerVatCode", customer["vat"])
    _child(document, "CustomerFiscalCode", customer["vat"])
    _child(document, "CustomerEInvoiceDestCode", customer["sdi"] or "0000000")
    if customer["pec"]:
        _child(document, "CustomerPec", customer["pec"])
    _child(document, "TotalWithoutTax", _money(data["net_cents"]))
    _child(document, "VatAmount", _money(data["vat_cents"]))
    _child(document, "Total", _money(data["gross_cents"]))
    _child(document, "PricesIncludeVat", "false")
    _child(document, "PaymentName", "PayPal")

    payments = ET.SubElement(document, "Payments")
    payment = ET.SubElement(payments, "Payment")
    _child(payment, "Advance", "false")
    _child(payment, "Date", data["paid_date"])
    _child(payment, "Amount", _money(data["gross_cents"]))
    _child(payment, "Paid", "true")

    _child(
        document,
        "InternalComment",
        f"QRFACILE ordine {data['order_id']} - PayPal capture {data['paypal_capture_id']}",
    )

    rows = ET.SubElement(document, "Rows")
    row = ET.SubElement(rows, "Row")
    _child(row, "Code", "QRFACILE-WINE")
    _child(row, "Description", data["description"])
    _child(row, "Qty", "1")
    _child(row, "Um", "pz")
    _child(row, "Price", _money(data["net_cents"]))
    rate = int(data["vat_rate"])
    vat_code = _child(row, "VatCode", rate)
    vat_code.set("Perc", str(rate))
    vat_code.set("Class", "Imponibile")
    vat_code.set("Description", f"Imponibile {rate}%")
    _child(row, "Total", _money(data["net_cents"]))
    _child(row, "Stock", "false")

    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_summary(data: Mapping[str, Any]) -> tuple[str, str]:
    customer = data["customer"]
    test = data["environment"] != "live"
    prefix = "[TEST SANDBOX - NON FATTURARE] " if test else ""
    subject = f"{prefix}Fattura da emettere - QRFACILE ordine {data['order_id']} - {customer['name']}"
    lines = []
    if test:
        lines += [
            "ATTENZIONE: pagamento di prova (ambiente PayPal non Live).",
            "NON emettere fattura e non importare il file in Danea.",
            "",
        ]
    lines += [
        "Pagamento ricevuto su QRFACILE: emettere la fattura elettronica.",
        "",
        f"Ordine QRFACILE: {data['order_id']}",
        f"Data pagamento: {data['paid_label']} (Europe/Rome)",
        f"Metodo: PayPal - capture {data['paypal_capture_id']}",
        "",
        "Cliente",
        f"  Ragione sociale: {customer['name']}",
        f"  Partita IVA: {customer['vat']}",
        f"  Codice SDI: {customer['sdi'] or '-'}",
        f"  PEC: {customer['pec'] or '-'}",
        f"  Indirizzo: {customer['address']}, {customer['postcode']} {customer['city']} ({customer['province']})",
        "",
        "Righe",
        f"  {data['description']}",
        f"  Imponibile: {_euro(data['net_cents'])}",
        f"  IVA {data['vat_rate']}%: {_euro(data['vat_cents'])}",
        f"  Totale incassato: {_euro(data['gross_cents'])}",
        "",
        "In allegato il file Easyfatt-Xml: in Danea Easyfatt usa",
        "Utilità > Importa documenti Easyfatt-Xml, controlla il documento",
        "e invialo allo SDI come di consueto.",
    ]
    return subject, "\n".join(lines) + "\n"


def build_message(data: Mapping[str, Any], to: str, cc: list[str]) -> EmailMessage:
    subject, body = build_summary(data)
    message = EmailMessage()
    message["To"] = to
    if cc:
        message["Cc"] = ", ".join(cc)
    message["Subject"] = subject
    message.set_content(body)
    message.add_attachment(
        build_easyfatt_xml(data),
        maintype="application",
        subtype="xml",
        filename=f"qrfacile-ordine-{data['order_id']}.DefXml",
    )
    return message


def send_invoice_handoff(order_id: int, *, force: bool = False) -> str:
    """Send the hand-off once per order. Returns a short, non-sensitive status."""
    recipients = load_recipients()
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM orders WHERE id=%s FOR UPDATE", (int(order_id),))
            order = cur.fetchone()
            if not order:
                return "order_not_found"
            if order.get("invoice_handoff_sent_at") and not force:
                conn.commit()
                return "already_sent"
            error = ""
            try:
                if recipients is None:
                    raise InvoiceHandoffError("recipients_not_configured")
                data = invoice_data(order)
                sent, error = send_email_message(build_message(data, *recipients))
                if not sent:
                    raise InvoiceHandoffError(error or "smtp_delivery_failed")
            except InvoiceHandoffError as exc:
                error = str(exc)
            cur.execute(
                """
                UPDATE orders
                SET invoice_handoff_attempts = COALESCE(invoice_handoff_attempts, 0) + 1,
                    invoice_handoff_sent_at = CASE WHEN %s THEN now() ELSE invoice_handoff_sent_at END,
                    invoice_handoff_last_error = %s
                WHERE id = %s
                """,
                (not error, error or None, int(order_id)),
            )
        conn.commit()
    return "sent" if not error else error


def handoff_after_payment(order_id: int | None) -> str:
    """Best-effort hook for the payment paths; never raises."""
    if not order_id:
        return "no_order"
    try:
        return send_invoice_handoff(int(order_id))
    except Exception:
        return "handoff_failed"
