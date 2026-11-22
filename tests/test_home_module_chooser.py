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
