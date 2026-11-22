"""Link module: fixes for the minor findings of the final review."""
from __future__ import annotations

import asyncio
import io

import pytest
from fastapi import HTTPException
from PIL import Image

from qrfacile_app.modules import switches
from tests.test_link_app_area import _create, _request, _upload, area  # noqa: F401 - fixture


def _png(size) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_huge_pixel_logo_is_rejected_before_decoding(tmp_path, monkeypatch):
    from qrfacile_app.modules.content_types import minipage
    from qrfacile_app.modules.content_types.base import ContentError

    monkeypatch.setattr(minipage, "get_uploads_dir", lambda: str(tmp_path))
    huge = _png((9000, 9000))  # 81 MP, tiny file
    with pytest.raises(ContentError):
        minipage.MiniPageType().parse({"minipage_title": "Bar"}, {"minipage_logo": _upload("l.png", huge)},
                                      None, qr_item_id=1)
    assert not list(tmp_path.rglob("*.png"))
    ok = minipage.MiniPageType().parse({"minipage_title": "Bar"}, {"minipage_logo": _upload("l.png", _png((800, 400)))},
                                       None, qr_item_id=1)
    assert ok["logo"].startswith("modules/link/1/logo-")


def test_module_files_are_not_served_by_the_public_uploads_mount():
    from qrfacile_app import main

    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": "GET", "scheme": "http", "path": "/uploads/modules/link/1/abc.pdf",
             "raw_path": b"/uploads/modules/link/1/abc.pdf", "query_string": b"", "root_path": "",
             "headers": [(b"host", b"testserver")], "server": ("testserver", 80), "client": ("t", 1),
             "http_version": "1.1"}
    asyncio.run(main.app(scope, receive, send))
    assert sent[0]["status"] == 404


def test_minipage_logo_is_served_through_the_resolver(monkeypatch, tmp_path):
    from qrfacile_app.modules import public as resolver
    from qrfacile_app.modules.content_types import minipage
    from tests.test_module_public_resolver import REQUEST, _install

    (tmp_path / "modules/link/3").mkdir(parents=True)
    (tmp_path / "modules/link/3/logo-x.png").write_bytes(_png((10, 10)))
    monkeypatch.setattr(minipage, "get_uploads_dir", lambda: str(tmp_path))
    monkeypatch.setattr(resolver, "get_uploads_dir", lambda: str(tmp_path))
    content = {"title": "Bar", "text": "", "buttons": [], "logo": "modules/link/3/logo-x.png"}
    rows = {"MINI": {"id": 3, "status": "attiva", "module": "link", "stats_level": "none",
                     "payload": {"type": "minipage", "content": {"minipage": content}}}}
    _install(monkeypatch, rows)
    html = resolver.resolve_module_qr(REQUEST, "MINI").body.decode()
    assert 'src="/d/MINI/logo"' in html and "/uploads/" not in html
    logo = resolver.module_logo(REQUEST, "MINI")
    assert logo.status_code == 200 and logo.media_type == "image/png"
    rows["MINI"]["status"] = "sospesa"
    assert resolver.module_logo(REQUEST, "MINI").status_code == 404


def test_historic_check_scans_are_not_counted(monkeypatch):
    from types import SimpleNamespace

    from qrfacile_app.modules import public as resolver
    from tests.test_module_public_resolver import _install

    _install(monkeypatch, {"AAA": {"id": 1, "status": "attiva", "module": "link", "stats_level": "detailed",
                                   "payload": {"type": "link", "content": {"link": {"url": "https://example.com"}}}}})
    calls = []
    monkeypatch.setattr(resolver, "record_scan", lambda cur, **kw: calls.append(kw))
    probe = SimpleNamespace(headers={"user-agent": "qrfacile-historic-qr-check"})
    assert resolver.resolve_module_qr(probe, "AAA").status_code == 302
    assert calls == []


@pytest.mark.integration
def test_replaced_files_are_deleted(area, tmp_path, monkeypatch):
    from qrfacile_app.modules.content_types import pdf

    monkeypatch.setattr(pdf, "get_uploads_dir", lambda: str(tmp_path))
    monkeypatch.setattr(area.ui, "get_uploads_dir", lambda: str(tmp_path))
    _create(area, kind="pdf")
    post = area.ui.link_content_post
    asyncio.run(post(_request({"type": "pdf", "pdf_file": _upload("a.pdf", b"%PDF-1.4 one")}), 1))
    first = area.sql("SELECT payload FROM qr_items")[0]["payload"]["content"]["pdf"]["file"]
    asyncio.run(post(_request({"type": "pdf", "pdf_file": _upload("b.pdf", b"%PDF-1.4 two")}), 1))
    second = area.sql("SELECT payload FROM qr_items")[0]["payload"]["content"]["pdf"]["file"]
    assert first != second
    assert not (tmp_path / first).exists() and (tmp_path / second).exists()
    asyncio.run(post(_request({"type": "pdf", "pdf_file": _upload("b.pdf", b"%PDF-1.4 two")}), 1))
    assert (tmp_path / second).exists()


def test_beta_create_redirects_when_link_on(monkeypatch):
    from qrfacile_app import external_qr_ui as ext

    monkeypatch.setattr(ext, "require_csrf_or_same_origin", lambda request: None)
    monkeypatch.setattr(ext, "require_any_role", lambda *a, **k: {"id": 1, "role": "winery"})
    monkeypatch.setattr(ext, "is_enabled", lambda key: True)
    monkeypatch.setattr(ext, "pg", lambda: pytest.fail("must not touch the database"))
    response = ext.new_external_create(_request(), target_url="https://example.com")
    assert response.status_code == 303 and response.headers["location"] == "/app/link/new"


def test_admin_gets_404_not_500_before_migration(monkeypatch):
    from qrfacile_app.modules.link import app_ui

    monkeypatch.setattr(app_ui, "require_any_role", lambda *a, **k: {"id": 1, "role": "admin"})
    monkeypatch.setattr(switches, "migration_applied", lambda: False)
    with pytest.raises(HTTPException) as exc:
        app_ui.link_list(_request())
    assert exc.value.status_code == 404
