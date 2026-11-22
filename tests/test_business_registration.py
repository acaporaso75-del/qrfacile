"""Business/professional accounts: register, land on Link, no wine entries."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from qrfacile_app import auth_routes, ui_shell


def _register_ui(monkeypatch, *, enabled=True, store=None):
    from qrfacile_app.modules.link import register_ui

    monkeypatch.setattr(register_ui, "is_enabled", lambda key: enabled)
    if store is not None:
        class Cur:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, params=None):
                store["sql"].append(" ".join(sql.split()))

            def fetchone(self):
                return {"id": 51}

        class Conn(Cur):
            def cursor(self, **_kwargs):
                return Cur()

            def commit(self):
                store["commits"] += 1

            def rollback(self):
                store["rollbacks"] += 1

        monkeypatch.setattr(register_ui, "pg", lambda: Conn())
        monkeypatch.setattr(register_ui, "record_registration_acceptances",
                            lambda cur, **kw: store["sql"].append("ACCEPTANCES"))
        monkeypatch.setattr(register_ui, "create_verification",
                            lambda **kw: store["verifications"].append(kw))
    return register_ui


REQUEST = SimpleNamespace(
    app=SimpleNamespace(state=SimpleNamespace(app_base_url="https://www.qrfacile.it")),
    url=SimpleNamespace(scheme="https"), headers={}, cookies={},
)
FORM = dict(email="Bar@Example.test", password="Lunga-Password-2026!", password_confirm="Lunga-Password-2026!",  # pragma: allowlist secret
            business_name="Bar Sport", terms_accepted="yes", privacy_acknowledged="yes")


def test_register_business_404_when_link_off(monkeypatch):
    ui = _register_ui(monkeypatch, enabled=False)
    with pytest.raises(HTTPException) as exc:
        ui.register_business_get(REQUEST)
    assert exc.value.status_code == 404
    with pytest.raises(HTTPException) as exc:
        ui.register_business_post(REQUEST, **FORM)
    assert exc.value.status_code == 404


def test_register_business_form_is_labelled(monkeypatch):
    import re

    ui = _register_ui(monkeypatch)
    monkeypatch.setattr(ui, "csrf_input", lambda request: "")
    html = ui.register_business_get(REQUEST).body.decode()
    labels = set(re.findall(r'<label for="([^"]+)"', html))
    for control in re.findall(r'<input[^>]*\bid="([^"]+)"', html):
        assert control in labels
    assert 'action="/register-business"' in html and "/terms" in html and "/privacy" in html


def test_register_business_creates_verified_required_user(monkeypatch):
    store = {"sql": [], "commits": 0, "rollbacks": 0, "verifications": []}
    ui = _register_ui(monkeypatch, store=store)
    response = ui.register_business_post(REQUEST, **FORM)
    assert response.status_code == 303 and response.headers["location"] == "/login?created=1"
    insert = next(sql for sql in store["sql"] if sql.startswith("INSERT INTO users"))
    assert "'business'" in insert and "email_verification_required" in insert
    assert not any("credit_ledger" in sql for sql in store["sql"])
    assert "ACCEPTANCES" in store["sql"] and store["commits"] == 1
    assert store["verifications"] == [{"user_id": 51, "base_url": "https://www.qrfacile.it"}]


@pytest.mark.parametrize("override, message", [
    ({"terms_accepted": ""}, "Termini"),
    ({"password_confirm": "altro"}, "coincidono"),  # pragma: allowlist secret
    ({"business_name": " "}, "nome"),
    ({"email": "nope"}, "Email"),
])
def test_register_business_rejects_bad_input(monkeypatch, override, message):
    from urllib.parse import unquote_plus

    store = {"sql": [], "commits": 0, "rollbacks": 0, "verifications": []}
    ui = _register_ui(monkeypatch, store=store)
    response = ui.register_business_post(REQUEST, **{**FORM, **override})
    assert response.status_code == 303 and message in unquote_plus(response.headers["location"])
    assert store["sql"] == []


def test_business_login_lands_on_link():
    assert auth_routes.default_landing("business") == "/app/link"
    assert auth_routes.default_landing("winery") == "/app/dashboard"
    assert auth_routes.default_landing("studio") == "/app/start"


def test_business_sidebar_has_no_wine_entries():
    html = ui_shell._sidebar("business", "bar@example.test", {"wine": 0, "generic": 7})
    for href in ("/app/link", "/app/billing", "/app/billing-profile", "/logout"):
        assert f'href="{href}"' in html
    for href in ("/app/dashboard", "/app/new-wine", "/app/new-wine-master", "/app/new-external", "/app/start"):
        assert f'href="{href}"' not in html
    assert "QR vino" not in html
    assert ui_shell._role_label("business") == "Azienda"


def test_business_billing_page_offers_only_link_pack(monkeypatch):
    from contextlib import nullcontext

    from qrfacile_app import billing_ui
    from starlette.requests import Request

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def cursor(self, **_kwargs):
            return nullcontext(None)

        def commit(self):
            pass

    monkeypatch.setattr(billing_ui, "pg", lambda: Conn())
    monkeypatch.setattr(billing_ui, "require_any_role",
                        lambda request, roles, **kw: {"id": 9, "email": "b@example.test", "role": "business"} if "business" in roles else pytest.fail("business not allowed"))
    for name, value in {
        "_cleanup_old_pending_orders": None, "_ledger": [], "_orders": [], "_active_subscription": None,
        "_recommended_pack_from_invite": None, "_annual_allowances": "",
    }.items():
        monkeypatch.setattr(billing_ui, name, lambda *a, _v=value, **k: _v)
    monkeypatch.setattr(billing_ui, "_balances", lambda *a, **k: {"wine": 0, "generic": 4})
    request = Request({"type": "http", "method": "GET", "scheme": "https", "path": "/app/billing",
                       "query_string": b"", "headers": [(b"host", b"www.qrfacile.it")],
                       "server": ("www.qrfacile.it", 443), "client": ("t", 1),
                       "app": SimpleNamespace(state=SimpleNamespace(app_base_url="https://www.qrfacile.it"))})
    html = billing_ui.billing(request).body.decode()
    assert 'value="generic_10"' in html
    for wine_pack in ("annual_start", "annual_pro", "start", "pro"):
        assert f'value="{wine_pack}"' not in html
    assert "QR vino disponibili" not in html and 'href="/app/dashboard"' not in html
