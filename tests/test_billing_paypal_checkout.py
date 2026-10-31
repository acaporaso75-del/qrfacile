import asyncio
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from qrfacile_app import paypal_ui
from qrfacile_app.billing_ui import _pack_card
from qrfacile_app.checkout_ui import paypal_checkout_form, paypal_checkout_script
from qrfacile_app.csrf_core import csrf_token_for_request
from qrfacile_app.pricing_config import get_purchase_pack
from qrfacile_app.security_middleware import SecurityHeadersMiddleware, paypal_checkout_origin

ROOT = Path(__file__).resolve().parents[1]


class _FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.max_depth = 0
        self.forms = []
        self.buttons = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "form":
            self.depth += 1
            self.max_depth = max(self.max_depth, self.depth)
            self.forms.append(values)
        elif tag == "button":
            self.buttons.append(values)

    def handle_endtag(self, tag):
        if tag == "form":
            self.depth -= 1


def _request(path: str = "/app/billing", method: str = "GET") -> Request:
    app = SimpleNamespace(state=SimpleNamespace(app_base_url="http://192.168.1.139:8001"))
    return Request({
        "type": "http",
        "method": method,
        "scheme": "http",
        "path": path,
        "query_string": b"",
        "headers": [
            (b"host", b"192.168.1.139:8001"),
            (b"cookie", b"session_token=test-session"),
        ],
        "server": ("192.168.1.139", 8001),
        "client": ("testclient", 123),
        "app": app,
    })


def test_online_billing_card_is_valid_post_form_with_csrf():
    request = _request()
    html = paypal_checkout_form(request, pack="generic_10")
    parser = _FormParser()
    parser.feed(html)

    assert parser.max_depth == 1
    assert parser.forms == [{
        "method": "post",
        "action": "/paypal/start",
        "data-paypal-checkout": None,
    }]
    assert parser.buttons[0]["type"] == "submit"
    assert "disabled" not in parser.buttons[0]
    assert 'name="pack" value="generic_10"' in html
    assert 'name="csrf_token"' in html


def test_rendered_billing_pack_uses_checkout_contract():
    html = _pack_card(_request(), "generic_10", get_purchase_pack("generic_10"))
    parser = _FormParser()
    parser.feed(html)
    assert parser.max_depth == 1
    assert parser.forms[0]["method"] == "post"
    assert parser.forms[0]["action"] == "/paypal/start"
    assert parser.buttons[0]["type"] == "submit"
    assert "Acquista ora" in html
    assert 'name="csrf_token"' in html


def test_every_paypal_checkout_surface_uses_shared_contract():
    for relative in (
        "qrfacile_app/billing_ui.py",
        "qrfacile_app/pricing_ui.py",
        "qrfacile_app/studio_area.py",
    ):
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "paypal_checkout_form(" in source
        assert "paypal_checkout_script()" in source
        assert 'action="/paypal/start"' not in source


def test_disabled_pack_has_no_enabled_submit_control():
    html = paypal_checkout_form(_request(), pack="unlimited", disabled=True)
    parser = _FormParser()
    parser.feed(html)
    assert "disabled" in parser.buttons[0]
    assert parser.buttons[0]["aria-disabled"] == "true"


def test_checkout_script_sets_loading_and_only_blocks_duplicate_submit():
    script = paypal_checkout_script()
    duplicate_guard = script.index("form.dataset.submitting === 'true'")
    prevented = script.index("event.preventDefault()")
    first_submit = script.index("form.dataset.submitting = 'true'")
    assert duplicate_guard < prevented < first_submit
    assert "Connessione a PayPal..." in script
    assert "button.disabled = true" in script
    assert "aria-busy" in script


def test_csp_checkout_origin_follows_paypal_mode(monkeypatch):
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    assert paypal_checkout_origin() == "https://www.sandbox.paypal.com"
    monkeypatch.setenv("PAYPAL_MODE", "live")
    assert paypal_checkout_origin() == "https://www.paypal.com"


def test_security_middleware_emits_sandbox_form_action(monkeypatch):
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    middleware = SecurityHeadersMiddleware(app=lambda *_args: None)

    async def call_next(_request):
        return Response("ok")

    response = asyncio.run(middleware.dispatch(_request(), call_next))
    csp = response.headers["Content-Security-Policy"]
    assert "form-action 'self' https://www.sandbox.paypal.com" in csp
    assert "https://www.paypal.com" not in csp


class _Cursor:
    def __init__(self, state):
        self.state = state
        self.last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=()):
        self.last_sql = " ".join(sql.split())
        self.state["queries"].append((self.last_sql, params))
        if self.state.get("fail_paypal_id_update") and "SET paypal_order_id" in self.last_sql:
            raise RuntimeError("database unavailable")

    def fetchone(self):
        if "AS profile" in self.last_sql:
            return {"profile": self.state.get("profile", {
                "name": "Cantina Test", "vat": "12345678903", "sdi": "ABC1234", "pec": "",
                "billing_address": "Via Test 1", "city": "Benevento", "billing_cap": "82100",
                "province": "BN", "billing_country": "IT",
            })}
        if "SELECT * FROM orders" in self.last_sql:
            return self.state.get("order")
        if "FROM wineries" in self.last_sql:
            return {"id": 9}
        if "RETURNING id" in self.last_sql:
            return {"id": 77}
        return {}


class _Connection:
    def __init__(self, state):
        self.state = state

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self, **_kwargs):
        return _Cursor(self.state)

    def commit(self):
        self.state["commits"] += 1


class _ProviderResponse:
    def __init__(self, status_code=201, payload=None, text=""):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.text = text

    def json(self):
        return self._payload


def _install_checkout_mocks(monkeypatch, provider_response):
    state = {"queries": [], "commits": 0, "posts": []}
    monkeypatch.setattr(paypal_ui, "require_any_role", lambda *_args: {"id": 42, "role": "winery"})
    monkeypatch.setattr(paypal_ui, "pg", lambda: _Connection(state))
    monkeypatch.setattr(paypal_ui, "_paypal_token", lambda: "sandbox-token")

    def post(url, **kwargs):
        state["posts"].append((url, kwargs))
        return provider_response

    monkeypatch.setattr(paypal_ui.requests, "post", post)
    return state


def test_paypal_start_rejects_missing_csrf_before_db_or_http(monkeypatch):
    touched = []
    monkeypatch.setattr(paypal_ui, "require_any_role", lambda *_args: {"id": 42, "role": "winery"})
    monkeypatch.setattr(paypal_ui, "pg", lambda: touched.append("db"))
    monkeypatch.setattr(paypal_ui.requests, "post", lambda *_args, **_kwargs: touched.append("http"))
    with pytest.raises(HTTPException) as exc:
        paypal_ui.paypal_start(_request("/paypal/start", "POST"), "generic_10", csrf_token="")
    assert exc.value.status_code == 403
    assert touched == []


def test_paypal_start_posts_sandbox_order_and_redirects_to_approve(monkeypatch):
    approve = "https://www.sandbox.paypal.com/checkoutnow?token=TEST"
    state = _install_checkout_mocks(
        monkeypatch,
        _ProviderResponse(payload={"id": "PP-77", "links": [{"rel": "approve", "href": approve}]}),
    )
    request = _request("/paypal/start", "POST")
    response = paypal_ui.paypal_start(
        request,
        "generic_10",
        csrf_token=csrf_token_for_request(request),
    )
    assert response.status_code == 303
    assert response.headers["location"] == approve
    assert state["posts"][0][0] == "https://api-m.sandbox.paypal.com/v2/checkout/orders"
    assert state["posts"][0][1]["headers"]["PayPal-Request-Id"] == "qrfacile-order-77"
    assert any("SET paypal_order_id" in sql for sql, _params in state["queries"])


@pytest.mark.parametrize("status_code", [400, 500, 503])
def test_provider_error_redirects_to_readable_billing_error(monkeypatch, status_code):
    state = _install_checkout_mocks(
        monkeypatch,
        _ProviderResponse(status_code=status_code, text="provider-secret-detail"),
    )
    request = _request("/paypal/start", "POST")
    response = paypal_ui.paypal_start(
        request,
        "generic_10",
        csrf_token=csrf_token_for_request(request),
    )
    location = unquote(response.headers["location"])
    assert response.status_code == 303
    assert location.startswith("/app/billing?err=")
    assert "temporaneamente" in location
    assert "provider-secret-detail" not in location
    assert any("status='cancelled'" in sql for sql, _params in state["queries"])


def test_network_error_redirects_without_raw_exception(monkeypatch):
    state = {"queries": [], "commits": 0}
    monkeypatch.setattr(paypal_ui, "require_any_role", lambda *_args: {"id": 42, "role": "winery"})
    monkeypatch.setattr(paypal_ui, "pg", lambda: _Connection(state))
    monkeypatch.setattr(paypal_ui, "_paypal_token", lambda: "sandbox-token")
    monkeypatch.setattr(
        paypal_ui.requests,
        "post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            paypal_ui.requests.RequestException("provider-secret-detail")
        ),
    )
    request = _request("/paypal/start", "POST")
    response = paypal_ui.paypal_start(
        request,
        "generic_10",
        csrf_token=csrf_token_for_request(request),
    )
    location = unquote(response.headers["location"])
    assert response.status_code == 303
    assert "temporaneamente" in location
    assert "provider-secret-detail" not in location
    assert any("status='cancelled'" in sql for sql, _params in state["queries"])


def test_rejects_non_sandbox_approve_host(monkeypatch):
    state = _install_checkout_mocks(
        monkeypatch,
        _ProviderResponse(payload={
            "id": "PP-77",
            "links": [{"rel": "approve", "href": "https://evil.example/checkout"}],
        }),
    )
    request = _request("/paypal/start", "POST")
    response = paypal_ui.paypal_start(
        request,
        "generic_10",
        csrf_token=csrf_token_for_request(request),
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/app/billing?err=")
    assert any("status='cancelled'" in sql for sql, _params in state["queries"])


@pytest.mark.parametrize("payload", [[], {"id": "PP-77", "links": {}}, {"id": "PP-77", "links": [None]}])
def test_malformed_provider_json_redirects_without_500(monkeypatch, payload):
    state = _install_checkout_mocks(monkeypatch, _ProviderResponse(payload=payload))
    request = _request("/paypal/start", "POST")
    response = paypal_ui.paypal_start(
        request,
        "generic_10",
        csrf_token=csrf_token_for_request(request),
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/app/billing?err=")
    assert any("status='cancelled'" in sql for sql, _params in state["queries"])


def test_local_order_update_failure_has_readable_redirect(monkeypatch):
    approve = "https://www.sandbox.paypal.com/checkoutnow?token=TEST"
    state = _install_checkout_mocks(
        monkeypatch,
        _ProviderResponse(payload={"id": "PP-77", "links": [{"rel": "approve", "href": approve}]}),
    )
    state["fail_paypal_id_update"] = True
    request = _request("/paypal/start", "POST")
    response = paypal_ui.paypal_start(
        request,
        "generic_10",
        csrf_token=csrf_token_for_request(request),
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/app/billing?err=")
    assert any("status='cancelled'" in sql for sql, _params in state["queries"])


def test_annual_start_uses_gross_price_and_immutable_snapshot(monkeypatch):
    import json
    state = _install_checkout_mocks(monkeypatch, _ProviderResponse(payload={
        "id": "PP-77", "links": [{"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=TEST"}],
    }))
    request = _request("/paypal/start", "POST")
    response = paypal_ui.paypal_start(request, "annual_start",
        csrf_token=csrf_token_for_request(request), fiscal_confirmation="IT_ORDINARY")
    assert response.status_code == 303
    assert state["posts"][0][1]["json"]["purchase_units"][0]["amount"]["value"] == "120.78"
    params = next(params for sql, params in state["queries"] if "INSERT INTO orders" in sql)
    snapshot = json.loads(params[-2])
    assert (snapshot["net_cents"], snapshot["vat_cents"], snapshot["gross_cents"]) == (9900, 2178, 12078)
    assert snapshot["wine_credits"] == 15
    assert snapshot["fiscal_confirmation"] == "IT_ORDINARY"


@pytest.mark.parametrize("pack,confirmation,country", [
    ("start", "IT_ORDINARY", "IT"), ("annual_start", "", "IT"),
    ("annual_start", "IT_ORDINARY", "FR"),
])
def test_ineligible_annual_checkout_never_contacts_provider(monkeypatch, pack, confirmation, country):
    state = _install_checkout_mocks(monkeypatch, _ProviderResponse())
    state["profile"] = {
        "name": "Cantina Test", "vat": "12345678903", "sdi": "ABC1234", "pec": "",
        "billing_address": "Via Test 1", "city": "Benevento", "billing_cap": "82100",
        "province": "BN", "billing_country": country,
    }
    request = _request("/paypal/start", "POST")
    if country == "FR" and pack == "annual_start" and confirmation == "IT_ORDINARY":
        response = paypal_ui.paypal_start(request, pack, csrf_token=csrf_token_for_request(request),
                                          fiscal_confirmation=confirmation)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/app/winery/settings?err=")
    else:
        with pytest.raises(HTTPException):
            paypal_ui.paypal_start(request, pack, csrf_token=csrf_token_for_request(request),
                                   fiscal_confirmation=confirmation)
    assert not state["posts"]
    assert not any("INSERT INTO orders" in sql for sql, _ in state["queries"])


def test_incomplete_fiscal_profile_never_creates_order_or_contacts_provider(monkeypatch):
    state = _install_checkout_mocks(monkeypatch, _ProviderResponse())
    state["profile"] = {"name": "Cantina Test", "vat": "12345678903", "billing_country": "IT"}
    request = _request("/paypal/start", "POST")
    response = paypal_ui.paypal_start(request, "annual_start",
                                      csrf_token=csrf_token_for_request(request),
                                      fiscal_confirmation="IT_ORDINARY")
    assert response.status_code == 303
    assert response.headers["location"].startswith("/app/winery/settings?err=")
    assert response.headers["location"].endswith("#profilo-fiscale")
    assert not state["posts"]
    assert not any("INSERT INTO orders" in sql for sql, _ in state["queries"])


def test_annual_capture_grants_once_and_paid_replay_has_no_http(monkeypatch):
    from qrfacile_app.annual_packages import annual_quote
    state = _install_checkout_mocks(monkeypatch, _ProviderResponse(payload={
        "id": "PP-77", "status": "COMPLETED", "purchase_units": [{
            "payments": {"captures": [{"id": "CAPTURE-TEST", "status": "COMPLETED",
                                      "amount": {"currency_code": "EUR", "value": "120.78"}}]},
        }],
    }))
    state["order"] = {
        "id": 77, "user_id": 42, "pack": "annual_start", "status": "pending",
        "amount_cents": 12078, "currency": "EUR", "paypal_order_id": "PP-77",
        "payment_environment": paypal_ui.PAYPAL_MODE,
        "commercial_snapshot": annual_quote("annual_start", "IT", "12345678903"),
    }
    request = _request("/paypal/return")
    response = paypal_ui.paypal_return(request, token="PP-77", order_id=77)
    assert response.status_code == 303
    grants = [(sql, params) for sql, params in state["queries"] if "annual_purchase" in sql]
    assert len(grants) == 1
    assert grants[0][1][:3] == (42, 15, 77)
    assert grants[0][1][4] > grants[0][1][3]
    state["order"]["status"] = "paid"
    paypal_ui.paypal_return(request, token="PP-77", order_id=77)
    assert len(state["posts"]) == 1
    assert len([sql for sql, _ in state["queries"] if "annual_purchase" in sql]) == 1


def test_studio_annual_purchase_requires_quote_before_db_or_provider(monkeypatch):
    state = _install_checkout_mocks(monkeypatch, _ProviderResponse())
    monkeypatch.setattr(paypal_ui, "require_any_role", lambda *_: {"id":42, "role":"studio"})
    request = _request("/paypal/start", "POST")
    response = paypal_ui.paypal_start(request, "annual_start",
        csrf_token=csrf_token_for_request(request), fiscal_confirmation="IT_ORDINARY")
    assert response.status_code == 303 and response.headers["location"].startswith("/support")
    assert not state["queries"] and not state["posts"]


def test_capture_wrong_gross_amount_never_marks_paid_or_grants(monkeypatch):
    from qrfacile_app.annual_packages import annual_quote
    state = _install_checkout_mocks(monkeypatch, _ProviderResponse(payload={
        "id":"PP-77", "status":"COMPLETED", "purchase_units":[{
            "payments":{"captures":[{"id":"CAP-TEST","status":"COMPLETED",
                                     "amount":{"currency_code":"EUR","value":"99.00"}}]}
        }],
    }))
    state["order"] = {
        "id":77, "user_id":42, "pack":"annual_start", "status":"pending",
        "amount_cents":12078, "currency":"EUR", "paypal_order_id":"PP-77",
        "payment_environment":paypal_ui.PAYPAL_MODE,
        "commercial_snapshot":annual_quote("annual_start","IT","12345678903"),
    }
    response = paypal_ui.paypal_return(_request("/paypal/return"), token="PP-77", order_id=77)
    assert response.status_code == 303
    assert "err=" in response.headers["location"]
    assert not any("status='paid'" in sql or "INSERT INTO credit_ledger" in sql for sql, _ in state["queries"])
