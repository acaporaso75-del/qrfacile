"""Public Link pages change only when the module is switched on."""
from __future__ import annotations

from types import SimpleNamespace

from qrfacile_app import landing_routes, pricing_ui
from qrfacile_app.modules import switches


def _request():
    from starlette.requests import Request

    return Request({"type": "http", "method": "GET", "scheme": "https", "path": "/", "query_string": b"",
                    "headers": [(b"host", b"www.qrfacile.it")], "server": ("www.qrfacile.it", 443),
                    "client": ("t", 1), "app": SimpleNamespace(state=SimpleNamespace(app_base_url="https://www.qrfacile.it"))})


def test_link_landing_changes_only_when_on(monkeypatch):
    monkeypatch.setattr(switches, "is_enabled", lambda key: False)
    off = landing_routes.link_home(_request()).body.decode()
    assert "In arrivo" in off and "/register-business" not in off
    monkeypatch.setattr(switches, "is_enabled", lambda key: True)
    on = landing_routes.link_home(_request()).body.decode()
    assert 'href="/register-business"' in on and "In arrivo" not in on
    assert "29" in on and "IVA inclusa" in on


def test_pricing_shows_link_pack_vat_included_when_on(monkeypatch):
    monkeypatch.setattr(switches, "is_enabled", lambda key: False)
    off = pricing_ui.pricing_page(_request()).body.decode()
    assert "QRFacile Link" not in off
    monkeypatch.setattr(switches, "is_enabled", lambda key: True)
    on = pricing_ui.pricing_page(_request()).body.decode()
    assert "QRFacile Link" in on and "€ 29" in on and "IVA inclusa" in on
    assert 'href="/register-business"' in on


def test_home_link_card_active_only_when_on(monkeypatch):
    monkeypatch.setattr(switches, "is_enabled", lambda key: False)
    off = landing_routes.home(_request()).body.decode()
    card_off = off.split("<b>Link Diretto</b>")[0].rsplit("moduleCard", 1)[1]
    assert "In arrivo" in card_off
    monkeypatch.setattr(switches, "is_enabled", lambda key: True)
    on = landing_routes.home(_request()).body.decode()
    card_on = on.split("<b>Link Diretto</b>")[0].rsplit('<article class="moduleCard', 1)[1]
    assert "Attivo" in card_on and "In arrivo" not in card_on
