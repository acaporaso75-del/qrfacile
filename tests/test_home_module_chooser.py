"""Home page: 'Cosa vuoi fare con il tuo QR?' tiles let visitors pick a module."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from starlette.requests import Request

from qrfacile_app import landing_routes


def _request(path: str = "/") -> Request:
    return Request({"type": "http", "method": "GET", "scheme": "https", "path": path, "query_string": b"",
                    "headers": [(b"host", b"www.qrfacile.it")], "server": ("www.qrfacile.it", 443),
                    "client": ("t", 1), "app": SimpleNamespace(state=SimpleNamespace(app_base_url="https://www.qrfacile.it"))})


def _home() -> str:
    return landing_routes.home(_request()).body.decode()


def test_home_starts_with_module_chooser():
    html = _home()
    assert html.index("<section", html.index("<main ")) == html.index('<section class="moduleChooser"')
    chooser = html.split('id="scegli"', 1)[1].split("</section>", 1)[0]
    assert '<h1 id="scegli-title">Cosa vuoi fare con il tuo QR?</h1>' in chooser
    assert 'id="moduli"' in chooser
    for title in ("Ho una cantina", "Ho un'attività", "Ho un ristorante", "Quiz e formazione", "Magazzino", "Eventi"):
        assert chooser.count(f"<h2>{title}</h2>") == 1
    for href in ("/wine", "/link", "/menu", "/quiz", "/warehouse", "/events"):
        assert chooser.count(f'href="{href}"') == 1
    assert 'href="/register-winery"' in chooser and 'href="/register-business"' not in chooser
    assert chooser.count("In arrivo") == 5
    assert html.count('<article class="chooserCard') == 6


def test_home_header_leads_to_the_module_choice():
    header = _home().split('class="row topbar-actions"', 1)[1].split("</div>", 1)[0]
    assert 'href="#scegli"' in header and "Scegli il tuo QR" in header
    assert 'href="/login"' in header and 'href="/pricing"' in header
    assert 'href="/register-winery"' not in header


def test_only_home_opts_into_the_wide_public_layout():
    assert 'class="publicWrap publicWrapWide"' in _home()
    assert 'class="publicWrap publicWrapWide"' not in landing_routes.wine_home(_request("/wine")).body.decode()


@pytest.mark.parametrize(("path", "page"), (
    ("/", landing_routes.home),
    ("/link", landing_routes.link_home),
    ("/menu", landing_routes.menu_home),
    ("/quiz", landing_routes.quiz_home),
    ("/warehouse", landing_routes.warehouse_home),
    ("/events", landing_routes.events_home),
))
def test_non_wine_landing_does_not_use_the_bottle_photo(path, page):
    assert "/static/qr3d.png" not in page(_request(path)).body.decode()


def test_wine_landing_retains_the_bottle_photo():
    assert "/static/qr3d.png" in landing_routes.wine_home(_request("/wine")).body.decode()


def test_mobile_topbar_buttons_are_compact_but_tappable():
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text(encoding="utf-8")
    mobile = css.split("@media(max-width:560px){", 1)[1].split("\n}\n", 1)[0]
    rule = mobile.split(".topbar .row .btn{", 1)[1].split("}", 1)[0]
    assert "width:auto" in rule and "min-height:44px" in rule
