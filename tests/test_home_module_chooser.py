"""Home page: 'Cosa vuoi fare con il tuo QR?' tiles let visitors pick a module."""
from __future__ import annotations

from types import SimpleNamespace

from starlette.requests import Request

from qrfacile_app import landing_routes


def _home() -> str:
    request = Request({"type": "http", "method": "GET", "scheme": "https", "path": "/", "query_string": b"",
                       "headers": [(b"host", b"www.qrfacile.it")], "server": ("www.qrfacile.it", 443),
                       "client": ("t", 1), "app": SimpleNamespace(state=SimpleNamespace(app_base_url="https://www.qrfacile.it"))})
    return landing_routes.home(request).body.decode()


def test_home_starts_with_module_chooser():
    html = _home()
    assert html.index('id="scegli"') < html.index("moduleIntro")
    chooser = html.split('id="scegli"', 1)[1].split("</section>", 1)[0]
    assert "Cosa vuoi fare con il tuo QR?" in chooser
    for title in ("Ho una cantina", "Ho un'attività", "Ho un ristorante", "Quiz e formazione", "Magazzino", "Eventi"):
        assert title in chooser
    assert 'href="/register-winery"' in chooser and 'href="/register-business"' not in chooser
    assert chooser.count("In arrivo") == 5
    assert 'href="#scegli"' in html


def test_home_header_leads_to_the_module_choice():
    header = _home().split('class="row topbar-actions"', 1)[1].split("</div>", 1)[0]
    assert 'href="#scegli"' in header and "Prova gratis" in header
    assert 'href="/login"' in header and 'href="/pricing"' in header
    assert 'href="/register-winery"' not in header


def test_mobile_topbar_buttons_are_compact_but_tappable():
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text(encoding="utf-8")
    mobile = css.split("@media(max-width:560px){", 1)[1].split("\n}\n", 1)[0]
    rule = mobile.split(".topbar .row .btn{", 1)[1].split("}", 1)[0]
    assert "width:auto" in rule and "min-height:44px" in rule
