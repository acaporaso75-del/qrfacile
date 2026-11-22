"""QRFacile Link purchases: VAT-included snapshot at checkout, Danea hand-off."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET

from qrfacile_app import paypal_ui
from qrfacile_app.csrf_core import csrf_token_for_request
from qrfacile_app.services import invoice_handoff as ih
from tests.test_billing_paypal_checkout import _Connection, _Cursor, _ProviderResponse, _request
from tests.test_invoice_handoff import PAID_AT

IT_PRIVATE = {"customer_type": "private", "country": "IT", "name": "Mario Rossi", "fiscal_code": "RSSMRA80A01H501U",
              "address": "Via Roma 1", "postcode": "82100", "city": "Benevento", "province": "BN"}
US_COMPANY = {"customer_type": "company", "country": "US", "name": "Acme Inc", "address": "1 Main St", "city": "Boston"}
DE_COMPANY = {"customer_type": "company", "country": "DE", "name": "Hans GmbH", "vat_number": "DE123456789",  # pragma: allowlist secret
              "address": "Hauptstr. 1", "postcode": "10115", "city": "Berlin", "vies_valid": True}


class _LinkCursor(_Cursor):
    def fetchone(self):
        if "FROM billing_profiles" in self.last_sql:
            return self.state.get("billing_profile")
        return super().fetchone()


class _LinkConnection(_Connection):
    def cursor(self, **_kwargs):
        return _LinkCursor(self.state)


def _install(monkeypatch, *, switches, profile=None, role="business"):
    state = {"queries": [], "commits": 0, "posts": [], "billing_profile": profile}
    monkeypatch.setattr(paypal_ui, "require_any_role", lambda *_a, **_k: {"id": 42, "role": role})
    monkeypatch.setattr(paypal_ui, "pg", lambda: _LinkConnection(state))
    monkeypatch.setattr(paypal_ui, "_paypal_token", lambda: "sandbox-token")
    monkeypatch.setattr(paypal_ui, "is_enabled", lambda key: switches.get(key, False))
    approve = "https://www.sandbox.paypal.com/checkoutnow?token=TEST"

    def post(url, **kwargs):
        state["posts"].append((url, kwargs))
        return _ProviderResponse(payload={"id": "PP-77", "links": [{"rel": "approve", "href": approve}]})

    monkeypatch.setattr(paypal_ui.requests, "post", post)
    return state


def _start(pack="generic_10"):
    request = _request("/paypal/start", "POST")
    return paypal_ui.paypal_start(request, pack, csrf_token=csrf_token_for_request(request))


def _order_insert(state):
    return next(params for sql, params in state["queries"] if sql.startswith("INSERT INTO orders"))


def test_link_purchase_requires_billing_profile_when_sales_on(monkeypatch):
    state = _install(monkeypatch, switches={"link_sales_it": True}, profile=None)
    response = _start()
    assert response.status_code == 303
    assert response.headers["location"].startswith("/app/billing-profile?next=/app/billing")
    assert not any(sql.startswith("INSERT INTO orders") for sql, _ in state["queries"])
    assert state["posts"] == []


def test_link_purchase_unchanged_when_sales_off(monkeypatch):
    state = _install(monkeypatch, switches={}, profile=None, role="winery")
    response = _start()
    assert response.status_code == 303
    params = _order_insert(state)
    assert params[3] == 2900 and params[5] is None


def test_link_snapshot_amount_matches_quote(monkeypatch):
    state = _install(monkeypatch, switches={"link_sales_it": True, "link_sales_foreign": True}, profile=US_COMPANY)
    _start()
    params = _order_insert(state)
    snapshot = json.loads(params[5])
    assert params[3] == 2377 == snapshot["gross_cents"]
    assert snapshot["kind"] == "link" and snapshot["pack"] == "generic_10" and snapshot["generic_credits"] == 10
    assert snapshot["wine_credits"] == 0 and snapshot["category"] == "extra_eu"
    assert snapshot["customer"]["name"] == "Acme Inc"
    assert state["posts"][0][1]["json"]["purchase_units"][0]["amount"]["value"] == "23.77"


def test_link_foreign_refused_when_foreign_sales_off(monkeypatch):
    state = _install(monkeypatch, switches={"link_sales_it": True}, profile=US_COMPANY)
    response = _start()
    assert response.status_code == 303 and "/app/billing?err=" in response.headers["location"]
    assert not any(sql.startswith("INSERT INTO orders") for sql, _ in state["queries"])


def _link_order(profile, quote):
    snapshot = {"version": "link-2026-11-22", "kind": "link", "pack": "generic_10", "name": "QR Link 10",
                "generic_credits": 10, "wine_credits": 0, **quote, "customer": profile}
    return {"id": 88, "status": "paid", "pack": "generic_10", "amount_cents": quote["gross_cents"],
            "payment_environment": "live", "paypal_capture_id": "CAP-9", "paid_at": PAID_AT,
            "commercial_snapshot": snapshot}


def _xml(order):
    root = ET.fromstring(ih.build_easyfatt_xml(ih.invoice_data(order)))
    return root.find("Documents/Document")


def test_invoice_xml_for_italian_private():
    from qrfacile_app.services.billing_profile import normalize_billing_profile
    from qrfacile_app.services.vat import link_quote

    profile = normalize_billing_profile(IT_PRIVATE)
    quote = link_quote(profile=profile, oss_threshold_exceeded=False, foreign_enabled=False)
    doc = _xml(_link_order(profile, quote))
    assert doc.findtext("CustomerFiscalCode") == "RSSMRA80A01H501U"
    assert doc.findtext("CustomerVatCode") == ""
    assert doc.findtext("CustomerEInvoiceDestCode") == "0000000"
    assert doc.findtext("Total") == "29.00" and doc.findtext("VatAmount") == "5.23"
    vat = doc.find("Rows/Row/VatCode")
    assert vat.get("Perc") == "22" and vat.get("Class") == "Imponibile"
    assert doc.findtext("Rows/Row/Code") == "QRFACILE-LINK"
    assert "QRFacile Link" in doc.findtext("Rows/Row/Description")


def test_invoice_xml_for_reverse_charge():
    from qrfacile_app.services.billing_profile import normalize_billing_profile
    from qrfacile_app.services.vat import link_quote

    profile = {**normalize_billing_profile(DE_COMPANY), "vies_valid": True}
    quote = link_quote(profile=profile, oss_threshold_exceeded=False, foreign_enabled=True)
    doc = _xml(_link_order(profile, quote))
    assert doc.findtext("CustomerEInvoiceDestCode") == "XXXXXXX"
    assert doc.findtext("CustomerVatCode") == "DE123456789"  # pragma: allowlist secret
    assert doc.findtext("Total") == "23.77" and doc.findtext("VatAmount") == "0.00"
    vat = doc.find("Rows/Row/VatCode")
    assert vat.get("Perc") == "0"
    note = quote["exemption_note"]
    assert note in doc.findtext("InternalComment") and note in doc.findtext("Rows/Row/Description")
    subject, body = ih.build_summary(ih.invoice_data(_link_order(profile, quote)))
    assert note in body


def test_business_accounts_can_buy_only_link_packs(monkeypatch):
    import pytest
    from fastapi import HTTPException

    state = _install(monkeypatch, switches={"link_sales_it": True}, profile=IT_PRIVATE)
    with pytest.raises(HTTPException) as exc:
        _start("annual_start")
    assert exc.value.status_code == 403
    assert not any(sql.startswith("INSERT INTO orders") for sql, _ in state["queries"])


def test_winery_buying_link_reuses_its_fiscal_profile(monkeypatch):
    state = _install(monkeypatch, switches={"link_sales_it": True}, profile=None, role="winery")
    state["profile"] = {
        "name": "Cantina Test srl", "vat": "12345678903", "sdi": "ABC1234", "pec": "",
        "billing_address": "Via Test 1", "city": "Benevento", "billing_cap": "82100",
        "province": "BN", "billing_country": "IT",
    }
    response = _start()
    assert response.status_code == 303 and "billing-profile" not in response.headers["location"]
    snapshot = json.loads(_order_insert(state)[5])
    assert snapshot["customer"]["name"] == "Cantina Test srl"
    assert snapshot["customer"]["vat_number"] == "12345678903" and snapshot["customer"]["sdi"] == "ABC1234"
    assert snapshot["gross_cents"] == 2900


def test_winery_with_incomplete_fiscal_profile_goes_to_billing_profile(monkeypatch):
    state = _install(monkeypatch, switches={"link_sales_it": True}, profile=None, role="winery")
    state["profile"] = {"name": "Cantina", "vat": "", "billing_country": "IT"}
    response = _start()
    assert response.headers["location"].startswith("/app/billing-profile?next=/app/billing")
