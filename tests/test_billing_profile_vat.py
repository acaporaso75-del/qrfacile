"""Billing profile normalization and VAT quote for QRFacile Link (VAT included)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from qrfacile_app import pricing_config
from qrfacile_app.services.billing_profile import normalize_billing_profile
from qrfacile_app.services.vat import link_quote

IT_COMPANY = {"customer_type": "company", "country": "IT", "name": "Bar Sport srl", "vat_number": "01234567897", "sdi": "ABC1234"}
IT_PRIVATE = {"customer_type": "private", "country": "IT", "name": "Mario Rossi", "fiscal_code": "RSSMRA80A01H501U"}
DE_PRIVATE = {"customer_type": "private", "country": "DE", "name": "Hans Muller"}
DE_COMPANY = {"customer_type": "company", "country": "DE", "name": "Hans GmbH", "vat_number": "DE123456789"}
US_COMPANY = {"customer_type": "company", "country": "US", "name": "Acme Inc"}


def _quote(profile, **kw):
    kw.setdefault("oss_threshold_exceeded", False)
    kw.setdefault("foreign_enabled", True)
    return link_quote(profile=profile, **kw)


def test_pricing_constants():
    assert pricing_config.LINK_PACK_KEY == "generic_10"
    pack = pricing_config.LEGACY_PACKS["generic_10"]
    assert pack["amount_cents"] == 2900 and pack["prices_include_vat"] is True
    assert pricing_config.OSS_THRESHOLD_CENTS == 1_000_000
    assert pricing_config.EU_VAT_RATES["DE"] == "19"
    assert set(pricing_config.FOREIGN_VAT_CODES) == {"eu_reverse_charge", "extra_eu", "eu_consumer_oss"}


@pytest.mark.parametrize("profile", [IT_COMPANY, IT_PRIVATE])
def test_italy_any_customer_pays_2900_with_22(profile):
    q = _quote(profile)
    assert (q["category"], q["vat_rate"], q["net_cents"], q["vat_cents"], q["gross_cents"]) == ("it", "22", 2377, 523, 2900)


def test_eu_consumer_under_threshold_uses_italian_22():
    q = _quote(DE_PRIVATE)
    assert (q["category"], q["vat_rate"], q["net_cents"], q["vat_cents"], q["gross_cents"]) == ("eu_consumer", "22", 2377, 523, 2900)


def test_eu_consumer_over_threshold_uses_destination_rate():
    q = _quote(DE_PRIVATE, oss_threshold_exceeded=True)
    assert (q["category"], q["vat_rate"], q["net_cents"], q["vat_cents"], q["gross_cents"]) == ("eu_consumer", "19", 2437, 463, 2900)
    assert q["vat_code"] == pricing_config.FOREIGN_VAT_CODES["eu_consumer_oss"]


def test_eu_business_vies_valid_reverse_charge():
    q = _quote({**DE_COMPANY, "vies_valid": True})
    assert (q["category"], q["vat_cents"], q["net_cents"], q["gross_cents"]) == ("eu_business_reverse_charge", 0, 2377, 2377)
    assert q["exemption_note"]


@pytest.mark.parametrize("vies", [False, None])
def test_eu_business_without_vies_is_refused(vies):
    with pytest.raises(HTTPException) as exc:
        _quote({**DE_COMPANY, "vies_valid": vies})
    assert exc.value.status_code == 422


def test_extra_eu_outside_scope():
    q = _quote(US_COMPANY)
    assert (q["category"], q["vat_cents"], q["net_cents"], q["gross_cents"]) == ("extra_eu", 0, 2377, 2377)


@pytest.mark.parametrize("profile", [DE_PRIVATE, US_COMPANY, {**DE_COMPANY, "vies_valid": True}])
def test_foreign_refused_when_foreign_sales_off(profile):
    with pytest.raises(HTTPException) as exc:
        _quote(profile, foreign_enabled=False)
    assert exc.value.status_code == 422
    assert _quote(IT_PRIVATE, foreign_enabled=False)["gross_cents"] == 2900


def test_profile_normalization():
    private = normalize_billing_profile({**IT_PRIVATE, "fiscal_code": " rssmra80a01h501u "})
    assert private["fiscal_code"] == "RSSMRA80A01H501U" and private["sdi"] == "0000000"
    company = normalize_billing_profile({**IT_COMPANY, "vat_number": "IT 01234567897", "sdi": "abc1234"})
    assert company["vat_number"] == "01234567897" and company["sdi"] == "ABC1234"
    assert normalize_billing_profile({**IT_COMPANY, "sdi": "", "pec": "bar@pec.it"})["pec"] == "bar@pec.it"
    association = normalize_billing_profile({"customer_type": "association", "country": "IT", "name": "Pro Loco", "fiscal_code": "92012345678"})
    assert association["fiscal_code"] == "92012345678"
    foreign = normalize_billing_profile({**DE_COMPANY, "country": "de", "address": "Hauptstr. 1"})
    assert foreign["country"] == "DE" and foreign["vat_number"] == "DE123456789"
    bad = [
        {**IT_COMPANY, "sdi": "", "pec": ""},
        {**IT_COMPANY, "vat_number": "01234567890"},
        {**IT_PRIVATE, "fiscal_code": "ABC"},
        {**IT_PRIVATE, "name": ""},
        {**IT_PRIVATE, "customer_type": "alien"},
        {**DE_PRIVATE, "country": "XX1"},
    ]
    for data in bad:
        with pytest.raises(HTTPException) as exc:
            normalize_billing_profile(data)
        assert exc.value.status_code == 422


class _Cur:
    def __init__(self, store):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.store["sql"].append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.store.get("profile")


class _Conn(_Cur):
    def cursor(self, **_kwargs):
        return _Cur(self.store)

    def commit(self):
        self.store["commits"] += 1


def _ui(monkeypatch, store):
    from qrfacile_app.modules import billing_ui

    monkeypatch.setattr(billing_ui, "pg", lambda: _Conn(store))
    monkeypatch.setattr(billing_ui, "require_any_role", lambda *a, **k: {"id": 9, "email": "b@example.test", "role": "business"})
    monkeypatch.setattr(billing_ui, "csrf_input", lambda request: "<input type='hidden' name='csrf_token' value='t'>")
    monkeypatch.setattr(billing_ui, "require_csrf_or_same_origin", lambda request: None)
    return billing_ui


def _form_request(data):
    from types import SimpleNamespace

    async def form():
        return data

    return SimpleNamespace(form=form, headers={}, cookies={})


def test_billing_profile_form_is_labelled_and_escaped(monkeypatch):
    store = {"sql": [], "commits": 0, "profile": {**IT_COMPANY, "name": "<b>Bar</b>"}}
    ui = _ui(monkeypatch, store)
    html = ui.billing_profile_get(_form_request({}), next="/app/link").body.decode()
    assert "<b>Bar</b>" not in html and "&lt;b&gt;Bar&lt;/b&gt;" in html
    import re

    ids = set(re.findall(r'<label for="([^"]+)"', html))
    for control_id in re.findall(r'<(?:input|select)[^>]*\bid="([^"]+)"', html):
        assert control_id in ids
    assert "name='csrf_token'" in html and 'name="next" value="/app/link"' in html


def test_billing_profile_post_saves_and_checks_vies(monkeypatch):
    import asyncio

    store = {"sql": [], "commits": 0, "profile": None}
    ui = _ui(monkeypatch, store)
    monkeypatch.setattr(ui, "vies_check", lambda country, number: True)
    response = asyncio.run(ui.billing_profile_post(_form_request({**DE_COMPANY, "next": "https://evil.test"})))
    assert response.status_code == 303 and response.headers["location"].startswith("/app/billing-profile?msg=")
    saved = [p for sql, p in store["sql"] if sql.startswith("INSERT INTO billing_profiles")]
    assert saved and True in saved[0] and store["commits"] == 1

    store["sql"].clear()
    bad = asyncio.run(ui.billing_profile_post(_form_request({**IT_COMPANY, "sdi": "", "pec": "", "next": "/app/link"})))
    assert bad.status_code == 303 and "err=" in bad.headers["location"]
    assert not [s for s, _ in store["sql"] if s.startswith("INSERT")]
