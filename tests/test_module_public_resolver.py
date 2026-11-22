"""Public /d/<slug> resolver: printed QR Link codes must always work."""
from __future__ import annotations

from types import SimpleNamespace

from qrfacile_app.modules import public as resolver


class _Cur:
    def __init__(self, store):
        self.store = store
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.sql, self.params = " ".join(sql.split()).lower(), params

    def fetchone(self):
        return self.store["rows"].get(self.params[0]) if self.params else None


class _Conn(_Cur):
    def cursor(self, **_kwargs):
        return _Cur(self.store)

    def commit(self):
        self.store["commits"] += 1


def _install(monkeypatch, rows):
    store = {"rows": rows, "commits": 0}
    monkeypatch.setattr(resolver, "pg", lambda: _Conn(store))
    return store


REQUEST = SimpleNamespace(headers={"user-agent": "Mozilla/5.0 (iPhone)", "accept-language": "it-IT"})


def test_unmigrated_beta_row_still_redirects(monkeypatch):
    _install(monkeypatch, {"AAA": {"id": 1, "status": "attiva", "payload": {"url": "https://example.com/x"},
                                   "module": None, "stats_level": None}})
    monkeypatch.setattr(resolver, "is_enabled", lambda key: False)
    response = resolver.resolve_module_qr(REQUEST, "AAA")
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/x"
    assert response.headers["cache-control"] == "no-store"


def test_pdf_and_minipage_are_served(monkeypatch, tmp_path):
    from qrfacile_app.modules.content_types import pdf

    (tmp_path / "modules/link/2").mkdir(parents=True)
    (tmp_path / "modules/link/2/abc.pdf").write_bytes(b"%PDF-1.4 test")
    monkeypatch.setattr(pdf, "get_uploads_dir", lambda: str(tmp_path))
    _install(monkeypatch, {
        "PDF": {"id": 2, "status": "attiva", "module": "link", "stats_level": "none",
                "payload": {"type": "pdf", "content": {"pdf": {"file": "modules/link/2/abc.pdf", "name": "listino.pdf"}}}},
        "MINI": {"id": 3, "status": "attiva", "module": "link", "stats_level": "none",
                 "payload": {"type": "minipage", "content": {"minipage": {"title": "Bar Sport", "text": "", "buttons": []}}}},
    })
    response = resolver.resolve_module_qr(REQUEST, "PDF")
    assert response.status_code == 200 and response.media_type == "application/pdf"
    html = resolver.resolve_module_qr(REQUEST, "MINI")
    assert html.status_code == 200 and "Bar Sport" in html.body.decode()


def test_draft_or_unknown_slug_is_404(monkeypatch):
    _install(monkeypatch, {
        "OFF": {"id": 4, "status": "bozza", "module": "link", "stats_level": "none",
                "payload": {"type": "link", "content": {"link": {"url": "https://example.com"}}}},
        "BAD": {"id": 5, "status": "attiva", "module": "link", "stats_level": "none",
                "payload": {"url": "javascript:alert(1)"}},
        "ODD": {"id": 6, "status": "attiva", "module": "link", "stats_level": "none",
                "payload": {"type": "nope", "content": {}}},
    })
    for slug in ("OFF", "BAD", "ODD", "MISSING", "", "x" * 80):
        response = resolver.resolve_module_qr(REQUEST, slug)
        assert response.status_code == 404
        assert "/segnala/" in response.body.decode() or not slug or len(slug) > 64


def test_stats_failure_does_not_block_redirect(monkeypatch):
    _install(monkeypatch, {"AAA": {"id": 1, "status": "attiva", "module": "link", "stats_level": "detailed",
                                   "payload": {"type": "link", "content": {"link": {"url": "https://example.com"}}}}})

    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(resolver, "record_scan", boom)
    response = resolver.resolve_module_qr(REQUEST, "AAA")
    assert response.status_code == 302


def test_stats_recorded_in_own_transaction(monkeypatch):
    store = _install(monkeypatch, {"AAA": {"id": 1, "status": "attiva", "module": "link", "stats_level": "counts",
                                           "payload": {"type": "link", "content": {"link": {"url": "https://example.com"}}}}})
    calls = []
    monkeypatch.setattr(resolver, "record_scan", lambda cur, **kw: calls.append(kw))
    resolver.resolve_module_qr(REQUEST, "AAA")
    assert calls and calls[0]["level"] == "counts" and calls[0]["qr_item_id"] == 1
    assert store["commits"] == 1


def test_e_forward_still_points_to_d():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "qrfacile_app" / "public.py").read_text(encoding="utf-8")
    assert 'RedirectResponse(f"/d/{quote(slug, safe=\'\')}", status_code=301)' in source


def test_resolver_is_mandatory_and_d_route_is_unique():
    from qrfacile_app import main

    assert "qrfacile_app.modules.public" in main.MANDATORY_ROUTERS

    def walk(routes):
        for route in routes:
            nested = getattr(route, "original_router", None)
            if nested is not None:
                yield from walk(nested.routes)
            else:
                yield route

    paths = [getattr(r, "path", "") for r in walk(main.app.routes)]
    assert paths.count("/d/{slug}") == 1
