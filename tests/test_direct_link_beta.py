"""QR Link (beta) codes must work: printed /e/ codes forward to /d/, which
redirects to the current destination; owners can change it and download
the QR."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from qrfacile_app import external_qr_ui as ext, main
from qrfacile_app import public

ROOT = Path(__file__).resolve().parents[1]


class _Cur:
    def __init__(self, rows):
        self.rows, self.q = rows, ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.q, self.params = " ".join(sql.split()).lower(), params

    def fetchone(self):
        return self.rows.get(self.params[0]) if self.params else None


class _Conn(_Cur):
    def cursor(self, **_kwargs):
        return _Cur(self.rows)


@pytest.mark.parametrize(
    "url, ok",
    [
        ("https://example.com/menu", True),
        ("http://example.com", True),
        ("javascript:alert(1)", False),
        ("ftp://example.com", False),
        ("https://", False),
        ("https://e.com/" + "a" * 2100, False),
    ],
)
def test_only_http_destinations_are_accepted(url, ok):
    assert ext._valid_target(url) is ok


def test_resolver_redirects_active_codes_without_caching(monkeypatch):
    rows = {
        "AAA": {"status": "attiva", "payload": {"url": "https://example.com/listino.pdf"}},
        "OFF": {"status": "bozza", "payload": {"url": "https://example.com"}},
        "BAD": {"status": "attiva", "payload": {"url": "javascript:alert(1)"}},
    }
    monkeypatch.setattr(ext, "pg", lambda: _Conn(rows))
    response = ext.direct_link_public("AAA")
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/listino.pdf"
    assert response.headers["cache-control"] == "no-store"
    for slug in ("OFF", "BAD", "MISSING", ""):
        assert ext.direct_link_public(slug).status_code == 404


def test_printed_beta_codes_under_e_forward_to_d():
    source = (ROOT / "qrfacile_app" / "public.py").read_text(encoding="utf-8")
    assert "SELECT 1 FROM qr_items WHERE slug=%s AND qr_type='external' LIMIT 1" in source
    assert 'RedirectResponse(f"/d/{quote(slug, safe=\'\')}", status_code=301)' in source


def test_new_codes_use_d_prefix_and_resolver_is_mandatory():
    source = (ROOT / "qrfacile_app" / "external_qr_ui.py").read_text(encoding="utf-8")
    assert 'public_path = f"/d/{slug}"' in source
    assert "qrfacile_app.external_qr_ui" in main.MANDATORY_ROUTERS
    legacy = (ROOT / "qrfacile_app" / "legacy_routes.py").read_text(encoding="utf-8")
    assert '"d",' in legacy and '"r",' in legacy


def test_detail_page_escapes_destination_and_offers_download(monkeypatch):
    evil = 'https://x.test/"><script>alert(1)</script>'
    rows = {5: {"id": 5, "owner_user_id": 7, "public_path": "/e/AAA", "payload": {"url": evil}, "slug": "AAA"}}

    class Cur(_Cur):
        def fetchone(self):
            if "credit" in self.q or "available_credit_ledger" in self.q:
                return {"bal": 0}
            return rows.get(self.params[0]) if self.params else None

        def fetchall(self):
            return []

    class Conn(Cur):
        def cursor(self, **_kwargs):
            return Cur(rows)

    monkeypatch.setattr(ext, "pg", lambda: Conn(rows))
    monkeypatch.setattr(ext, "require_any_role", lambda *a, **k: {"id": 7, "email": "a@example.test", "role": "winery"})
    monkeypatch.setattr(ext, "_balances", lambda cur, uid: {"wine": 0, "generic": 0})
    monkeypatch.setattr(ext, "csrf_input", lambda request: "<input type='hidden' name='csrf_token' value='t'>")
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(app_base_url="https://www.qrfacile.it")),
        url=SimpleNamespace(scheme="https"), headers={}, cookies={},
    )
    html = ext.external_detail(request, 5).body.decode()
    assert "<script>alert(1)</script>" not in html
    assert "https://www.qrfacile.it/d/AAA" in html
    assert "/app/external/5/qr.pdf" in html and 'action="/app/external/5/target"' in html
