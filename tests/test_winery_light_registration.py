"""Cantina sign-up asks only for what the free trial needs."""
from __future__ import annotations

import re
from types import SimpleNamespace
from urllib.parse import unquote_plus

import pytest
from fastapi import HTTPException

from qrfacile_app import winery_register_routes as reg


class _Cursor:
    def __init__(self, store):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.store.append((" ".join(sql.split()), params))

    def fetchone(self):
        return {"id": len(self.store)}


class _Connection:
    def __init__(self):
        self.statements = []
        self.committed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **_kwargs):
        return _Cursor(self.statements)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


def _request():
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(app_base_url="https://example.test")),
        url=SimpleNamespace(scheme="https"),
        headers={},
        client=SimpleNamespace(host="127.0.0.1"),
    )


def _post(monkeypatch, **overrides):
    connection = _Connection()
    monkeypatch.setattr(reg, "pg", lambda: connection)
    monkeypatch.setattr(reg, "record_registration_acceptances", lambda *a, **k: None)
    monkeypatch.setattr(reg, "create_verification", lambda **k: None)
    form = dict(
        request=_request(),
        email="Nuova@Cantina.it",
        password="una-password-lunga",  # pragma: allowlist secret
        password_confirm="una-password-lunga",  # pragma: allowlist secret
        name="Cantina Prova",
        vat="",
        sdi="",
        pec="",
        phone="",
        contact_name="",
        contact_phone="",
        billing_address="",
        city="",
        billing_cap="",
        province="",
        billing_country="IT",
        terms_accepted="yes",
        privacy_acknowledged="yes",
        invite="",
        next="",
    )
    form.update(overrides)
    response = reg.register_winery_post(**form)
    return response, connection


def _winery_insert(connection):
    return next(params for sql, params in connection.statements if sql.startswith("INSERT INTO wineries"))


def test_minimal_signup_creates_account_with_empty_billing_profile(monkeypatch):
    response, connection = _post(monkeypatch)

    assert response.status_code == 303
    assert response.headers["location"] == "/login?created=1"
    assert connection.committed
    params = _winery_insert(connection)
    assert params[1] == "Cantina Prova"
    # vat, sdi, pec, phone, city, province, address, cap stored empty; country IT
    assert params[2:10] == ("", "", "", "", "", "", "", "")
    assert params[10] == "IT"
    assert any("credit_ledger" in sql for sql, _ in connection.statements)


def test_partial_billing_profile_is_rejected_before_any_write(monkeypatch):
    response, connection = _post(monkeypatch, vat="IT12345678903")

    assert response.status_code == 303
    assert "err=" in response.headers["location"]
    assert connection.statements == []


def test_complete_billing_profile_is_normalized_at_signup(monkeypatch):
    response, connection = _post(
        monkeypatch,
        vat="IT 01234567897",
        sdi="abc1234",
        billing_address="Via Roma 1",
        city="Benevento",
        billing_cap="82100",
        province="bn",
    )
    assert "err=" not in response.headers["location"], unquote_plus(response.headers["location"])
    params = _winery_insert(connection)
    assert params[2] == "01234567897"
    assert params[3] == "ABC1234"
    assert params[7] == "BN"


def test_blank_winery_name_is_rejected(monkeypatch):
    response, connection = _post(monkeypatch, name="   ")
    assert "err=" in response.headers["location"]
    assert connection.statements == []


def test_registration_helper_enforces_full_profile_when_started():
    assert reg.registration_fiscal_fields(name="X")["vat"] == ""
    with pytest.raises(HTTPException):
        reg.registration_fiscal_fields(name="X", city="Benevento")


def test_form_requires_only_trial_fields_and_keeps_billing_optional():
    page = reg.register_winery_get(_request()).body.decode()
    form = page[page.index('<form method="post" action="/register-winery"'):page.index("</form>")]
    required = set(re.findall(r'name="([a-z_]+)"[^>]*\brequired\b', form))
    assert required == {"email", "password", "password_confirm", "name", "terms_accepted", "privacy_acknowledged"}
    assert "<details" in form and "facoltativi" in form
    assert 'name="contact_name"' not in form


def test_wine_choice_leads_to_free_signup_without_future_tense():
    from starlette.requests import Request
    from qrfacile_app.landing_routes import home

    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})
    html = home(request).body.decode()
    wine_choice = html.split('<article class="chooserCard active">', 1)[1].split("</article>", 1)[0]
    assert 'href="/register-winery"' in wine_choice
    assert "3 QR gratis" in wine_choice
    assert "avra il proprio flusso" not in html
