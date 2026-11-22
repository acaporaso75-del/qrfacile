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


def _chooser(html: str) -> str:
    return html.split('id="scegli"', 1)[1].split("</section>", 1)[0]


def test_home_starts_with_module_chooser(monkeypatch):
    monkeypatch.setattr(switches, "is_enabled", lambda key: False)
    html = landing_routes.home(_request()).body.decode()
    assert html.index('id="scegli"') < html.index("moduleIntro")
    chooser = _chooser(html)
    assert "Cosa vuoi fare con il tuo QR?" in chooser
    for title in ("Ho una cantina", "Ho un'attività", "Ho un ristorante", "Quiz e formazione", "Magazzino", "Eventi"):
        assert title in chooser
    assert 'href="/register-winery"' in chooser
    assert 'href="/register-business"' not in chooser
    assert chooser.count("In arrivo") == 5
    assert 'href="#scegli"' in html


def test_home_chooser_link_card_follows_switch(monkeypatch):
    monkeypatch.setattr(switches, "is_enabled", lambda key: True)
    chooser = _chooser(landing_routes.home(_request()).body.decode())
    assert 'href="/register-business"' in chooser
    assert chooser.count("In arrivo") == 4
