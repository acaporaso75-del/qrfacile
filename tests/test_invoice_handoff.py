"""Paid orders are handed to the billing office with a Danea Easyfatt file."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import psycopg
import pytest
from psycopg.types.json import Jsonb

from qrfacile_app.services import invoice_handoff as ih


ROOT = Path(__file__).resolve().parents[1]
PAID_AT = int(datetime(2026, 11, 21, 23, 30, tzinfo=ZoneInfo("Europe/Rome")).timestamp())


def _snapshot(**overrides):
    snapshot = {
        "version": "wine-annual-2026-10-25", "pack": "annual_start", "name": "Start",
        "annual": True, "wine_credits": 15, "generic_credits": 0,
        "net_cents": 9900, "vat_cents": 2178, "vat_rate": "22", "gross_cents": 12078,
        "currency": "EUR", "billing_country": "IT", "vat_number": "01234567897",
        "customer": {
            "name": "Cantina Prova & Figli S.r.l.", "vat": "01234567897", "sdi": "ABC1234",
            "pec": "", "billing_address": "Via Roma 1", "city": "Benevento",
            "billing_cap": "82100", "province": "BN", "billing_country": "IT",
        },
    }
    snapshot.update(overrides)
    return snapshot


def _order(**overrides):
    order = {
        "id": 77, "status": "paid", "pack": "annual_start", "amount_cents": 12078,
        "payment_environment": "live", "paypal_capture_id": "CAP-1", "paid_at": PAID_AT,
        "commercial_snapshot": _snapshot(),
    }
    order.update(overrides)
    return order


def test_recipients_come_only_from_environment():
    assert ih.load_recipients({}) is None
    assert ih.load_recipients({"QRFACILE_INVOICE_TO": "not-an-email"}) is None
    assert ih.load_recipients({"QRFACILE_INVOICE_TO": "a@example.test"}) == ("a@example.test", [])
    assert ih.load_recipients({
        "QRFACILE_INVOICE_TO": "a@example.test",
        "QRFACILE_INVOICE_CC": "b@example.test, a@example.test",
    }) == ("a@example.test", ["b@example.test"])
    assert ih.load_recipients({"QRFACILE_INVOICE_TO": "a@example.test", "QRFACILE_INVOICE_CC": "bad"}) is None


def test_invoice_data_uses_frozen_snapshot_and_rome_date():
    data = ih.invoice_data(_order())
    assert data["customer"]["name"] == "Cantina Prova & Figli S.r.l."
    assert (data["net_cents"], data["vat_cents"], data["gross_cents"]) == (9900, 2178, 12078)
    # 23:30 in Rome is already the next day in UTC: the invoice date stays local.
    assert data["paid_date"] == "2026-11-21"


@pytest.mark.parametrize(
    "order, reason",
    [
        (_order(status="pending"), "order_not_paid"),
        (_order(commercial_snapshot=None), "fiscal_snapshot_missing"),
        (_order(amount_cents=10000), "amounts_inconsistent"),
        (_order(commercial_snapshot=_snapshot(vat_cents=1)), "amounts_inconsistent"),
        (_order(paid_at=None), "paid_at_missing"),
    ],
)
def test_invoice_data_refuses_unsafe_orders(order, reason):
    with pytest.raises(ih.InvoiceHandoffError, match=reason):
        ih.invoice_data(order)


def test_easyfatt_xml_describes_one_invoice_with_net_price_and_vat():
    root = ET.fromstring(ih.build_easyfatt_xml(ih.invoice_data(_order())))
    assert root.tag == "EasyfattDocuments"
    assert root.findtext("Company/VatCode") == "01413300623"
    documents = root.findall("Documents/Document")
    assert len(documents) == 1
    doc = documents[0]
    assert doc.findtext("DocumentType") == "I"
    assert doc.findtext("Date") == "2026-11-21"
    assert doc.find("Number") is None  # Easyfatt assigns its own numbering
    assert doc.findtext("CustomerName") == "Cantina Prova & Figli S.r.l."
    assert doc.findtext("CustomerVatCode") == "01234567897"
    assert doc.findtext("CustomerEInvoiceDestCode") == "ABC1234"
    assert doc.findtext("PricesIncludeVat") == "false"
    assert (doc.findtext("TotalWithoutTax"), doc.findtext("VatAmount"), doc.findtext("Total")) == (
        "99.00", "21.78", "120.78",
    )
    assert doc.findtext("Payments/Payment/Amount") == "120.78"
    assert doc.findtext("Payments/Payment/Paid") == "true"
    row = doc.find("Rows/Row")
    assert row.findtext("Price") == "99.00"
    assert row.findtext("Qty") == "1"
    vat = row.find("VatCode")
    assert (vat.text, vat.get("Perc"), vat.get("Class")) == ("22", "22", "Imponibile")
    assert "15 unità" in row.findtext("Description")


def test_pec_only_customer_uses_generic_sdi_code():
    customer = dict(_snapshot()["customer"], sdi="", pec="cantina@pec.example.test")
    doc = ET.fromstring(ih.build_easyfatt_xml(ih.invoice_data(
        _order(commercial_snapshot=_snapshot(customer=customer))
    ))).find("Documents/Document")
    assert doc.findtext("CustomerEInvoiceDestCode") == "0000000"
    assert doc.findtext("CustomerPec") == "cantina@pec.example.test"


def test_sandbox_orders_are_clearly_marked_not_to_invoice():
    subject, body = ih.build_summary(ih.invoice_data(_order(payment_environment="sandbox")))
    assert subject.startswith("[TEST SANDBOX - NON FATTURARE]")
    assert "NON emettere fattura" in body
    live_subject, live_body = ih.build_summary(ih.invoice_data(_order()))
    assert "SANDBOX" not in live_subject and "NON emettere" not in live_body
    assert "Imponibile: € 99,00" in live_body and "Totale incassato: € 120,78" in live_body


def test_message_has_cc_and_defxml_attachment():
    message = ih.build_message(ih.invoice_data(_order()), "a@example.test", ["b@example.test"])
    assert message["To"] == "a@example.test" and message["Cc"] == "b@example.test"
    attachments = list(message.iter_attachments())
    assert [a.get_filename() for a in attachments] == ["qrfacile-ordine-77.DefXml"]
    assert ET.fromstring(attachments[0].get_content()).tag == "EasyfattDocuments"


def test_payment_paths_schedule_handoff_after_commit():
    source = (ROOT / "qrfacile_app" / "paypal_ui.py").read_text(encoding="utf-8")
    assert "BackgroundTask(handoff_after_payment, order_id)" in source
    assert 'BackgroundTask(handoff_after_payment, int(locked_order["id"]))' in source


def test_handoff_hook_never_raises(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("database down")

    monkeypatch.setattr(ih, "send_invoice_handoff", boom)
    assert ih.handoff_after_payment(5) == "handoff_failed"
    assert ih.handoff_after_payment(None) == "no_order"


def _database_url() -> str:
    url = os.getenv("QRFACILE_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("QRFACILE_TEST_DATABASE_URL non configurata")
    parsed = urlsplit(url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("I test database possono contattare soltanto PostgreSQL locale")
    if not parsed.path.lstrip("/").startswith("qrfacile_test_"):
        pytest.fail("Il database temporaneo deve iniziare con qrfacile_test_")
    return url


@pytest.mark.integration
def test_handoff_is_sent_once_and_failures_are_recorded(monkeypatch):
    url = _database_url()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(
            """
            CREATE TABLE orders (
                id bigserial PRIMARY KEY, user_id bigint, pack text, amount_cents integer,
                status text, payment_environment text, paypal_capture_id text,
                paid_at bigint, commercial_snapshot jsonb
            )
            """
        )
        conn.execute((ROOT / "sql" / "2026_order_invoice_handoff.sql").read_text(encoding="utf-8"))
        order_id = conn.execute(
            """
            INSERT INTO orders (user_id, pack, amount_cents, status, payment_environment,
                                paypal_capture_id, paid_at, commercial_snapshot)
            VALUES (1, 'annual_start', 12078, 'paid', 'live', 'CAP-1', %s, %s) RETURNING id
            """,
            (PAID_AT, Jsonb(_snapshot())),
        ).fetchone()[0]

    sent = []
    monkeypatch.setattr(ih, "pg", lambda: psycopg.connect(url))
    monkeypatch.setenv("QRFACILE_INVOICE_TO", "billing@example.test")
    monkeypatch.setenv("QRFACILE_INVOICE_CC", "cc@example.test")

    monkeypatch.setattr(ih, "send_email_message", lambda message: (False, "smtp_delivery_failed"))
    assert ih.send_invoice_handoff(order_id) == "smtp_delivery_failed"

    monkeypatch.setattr(ih, "send_email_message", lambda message: (sent.append(message) or True, ""))
    assert ih.send_invoice_handoff(order_id) == "sent"
    assert ih.send_invoice_handoff(order_id) == "already_sent"
    assert ih.handoff_after_payment(order_id) == "already_sent"
    assert len(sent) == 1 and sent[0]["Cc"] == "cc@example.test"

    with psycopg.connect(url) as conn:
        sent_at, attempts, last_error = conn.execute(
            "SELECT invoice_handoff_sent_at, invoice_handoff_attempts, invoice_handoff_last_error FROM orders WHERE id=%s",
            (order_id,),
        ).fetchone()
    assert sent_at is not None and attempts == 2 and last_error is None

    assert ih.send_invoice_handoff(order_id, force=True) == "sent"
    assert len(sent) == 2


def test_admin_page_lists_paid_orders_with_download_and_resend(monkeypatch):
    from types import SimpleNamespace
    from qrfacile_app import admin_invoice_handoff_ui as ui

    rows = [
        {"o": dict(_order(), invoice_handoff_sent_at=None, invoice_handoff_last_error="smtp_delivery_failed")},
        {"o": dict(_order(id=78, commercial_snapshot=None, pack="start"))},
    ]

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, *_args):
            pass

        def fetchall(self):
            return rows

    class _Conn(_Cursor):
        def cursor(self, **_kwargs):
            return _Cursor()

    monkeypatch.setattr(ui, "pg", lambda: _Conn())
    monkeypatch.setattr(ui, "require_any_role", lambda *_a, **_k: {"email": "admin@example.test"})
    monkeypatch.setattr(ui, "csrf_input", lambda _request: '<input type="hidden" name="csrf_token" value="t">')
    monkeypatch.setenv("QRFACILE_INVOICE_TO", "billing@example.test")

    html = ui.invoice_handoff_page(SimpleNamespace(cookies={})).body.decode()
    assert "/admin/invoices/77/easyfatt.DefXml" in html
    assert 'action="/admin/invoices/77/send"' in html and 'name="csrf_token"' in html
    assert "Cantina Prova &amp; Figli S.r.l." in html and "€ 120.78" in html
    assert "Invio e-mail non riuscito" in html
    assert "/admin/invoices/78/easyfatt.DefXml" not in html
    assert "fattura manuale" in html
