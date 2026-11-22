"""Customer area of QRFacile Link: create, edit, publish, download."""
from __future__ import annotations

import asyncio
import io
from types import SimpleNamespace

import psycopg
import pytest
from fastapi import HTTPException
from psycopg.rows import dict_row

from qrfacile_app.modules import switches
from tests.test_vertical_modules_migration import MIGRATION, _database_url

pytestmark = pytest.mark.integration

USER = {"id": 1, "email": "bar@example.test", "role": "business"}


@pytest.fixture()
def area(monkeypatch):
    url = _database_url()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(
            """
            CREATE TABLE users (id bigserial PRIMARY KEY, email text, role text NOT NULL);
            INSERT INTO users (email, role) VALUES ('bar@example.test', 'winery'), ('other@example.test', 'winery');
            CREATE TABLE qr_items (
              id bigserial PRIMARY KEY, owner_user_id bigint, winery_id bigint, qr_type text, status text,
              slug text UNIQUE, title text, has_back int DEFAULT 0, public_path text, payload jsonb,
              created_at bigint, updated_at bigint
            );
            CREATE TABLE credit_ledger (
              id bigserial PRIMARY KEY, user_id bigint, credit_type text, delta int, reason text,
              ref_table text, ref_id bigint, created_at bigint
            );
            CREATE VIEW available_credit_ledger AS SELECT * FROM credit_ledger;
            CREATE TABLE legal_acceptances (
              id bigserial PRIMARY KEY, user_id bigint, document_key text NOT NULL, document_version text NOT NULL,
              accepted_at timestamptz NOT NULL DEFAULT now(), ip_address inet, user_agent text,
              evidence jsonb NOT NULL DEFAULT '{}'::jsonb, UNIQUE (user_id, document_key, document_version)
            );
            INSERT INTO legal_acceptances (user_id, document_key, document_version)
            VALUES (1, 'terms', '2026-12-link'), (1, 'privacy', '2026-12-link');
            """
        )
        conn.execute(MIGRATION.read_text(encoding="utf-8"))
        conn.execute("UPDATE users SET role='business' WHERE id=1")

    from qrfacile_app.modules.link import app_ui

    state = {"enabled": True}
    monkeypatch.setattr(switches, "is_enabled", lambda key: state["enabled"])
    monkeypatch.setattr(switches, "migration_applied", lambda: True)
    monkeypatch.setattr(app_ui, "pg", lambda: psycopg.connect(url, row_factory=dict_row))
    monkeypatch.setattr(app_ui, "require_any_role", lambda *a, **k: dict(USER))
    monkeypatch.setattr(app_ui, "csrf_input", lambda request: "<input type='hidden' name='csrf_token' value='t'>")
    monkeypatch.setattr(app_ui, "require_csrf_or_same_origin", lambda request: None)

    def sql(query, params=()):
        with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
            cur = conn.execute(query, params)
            return cur.fetchall() if cur.description else None

    return SimpleNamespace(ui=app_ui, sql=sql, state=state, url=url)


def _request(form=None):
    async def get_form():
        return form or {}

    return SimpleNamespace(
        form=get_form, headers={}, cookies={},
        app=SimpleNamespace(state=SimpleNamespace(app_base_url="https://www.qrfacile.it")),
        url=SimpleNamespace(scheme="https"),
    )


def _create(area, name="Menu bar", kind="link"):
    response = area.ui.link_new_post(_request(), name=name, kind=kind)
    assert response.status_code == 303
    return response


def _upload(name, data):
    return SimpleNamespace(filename=name, file=io.BytesIO(data))


def test_link_area_404_when_off_for_customers(area):
    area.state["enabled"] = False
    for call in (lambda: area.ui.link_list(_request()), lambda: area.ui.link_new_get(_request())):
        with pytest.raises(HTTPException) as exc:
            call()
        assert exc.value.status_code == 404


def test_empty_list_shows_first_use_guide(area):
    html = area.ui.link_list(_request()).body.decode()
    assert "Crea un QR" in html and 'href="/app/link/new"' in html
    assert "1." in html and "3." in html


def test_create_uses_free_quota_then_credit(area):
    for index in range(3):
        _create(area, name=f"QR {index}")
    assert area.sql("SELECT COUNT(*) AS n FROM credit_ledger")[0]["n"] == 0
    no_credit = area.ui.link_new_post(_request(), name="Quarto", kind="link")
    assert no_credit.headers["location"].startswith("/app/billing")
    assert area.sql("SELECT COUNT(*) AS n FROM qr_items")[0]["n"] == 3

    area.sql("INSERT INTO credit_ledger (user_id, credit_type, delta, reason, created_at) VALUES (1,'generic',10,'purchase',0)")
    response = _create(area, name="Quarto")
    rows = area.sql("SELECT * FROM qr_items ORDER BY id")
    assert len(rows) == 4
    new = rows[-1]
    assert new["module"] == "link" and new["status"] == "bozza" and new["title"] == "Quarto"
    assert new["public_path"] == f"/d/{new['slug']}" and new["payload"]["type"] == "link"
    assert response.headers["location"] == f"/app/link/{new['id']}"
    debit = area.sql("SELECT delta, credit_type, ref_id FROM credit_ledger WHERE delta < 0")
    assert debit == [{"delta": -1, "credit_type": "generic", "ref_id": new["id"]}]


def test_switching_type_keeps_other_content(area, tmp_path, monkeypatch):
    from qrfacile_app.modules.content_types import pdf

    monkeypatch.setattr(pdf, "get_uploads_dir", lambda: str(tmp_path))
    _create(area)
    qr_id = area.sql("SELECT id FROM qr_items")[0]["id"]
    post = area.ui.link_content_post
    asyncio.run(post(_request({"type": "link", "link_url": "https://example.com/menu"}), qr_id))
    asyncio.run(post(_request({"type": "pdf", "pdf_file": _upload("Listino.pdf", b"%PDF-1.4 x")}), qr_id))
    payload = area.sql("SELECT payload FROM qr_items WHERE id=%s", (qr_id,))[0]["payload"]
    assert payload["type"] == "pdf"
    assert payload["content"]["link"] == {"url": "https://example.com/menu"}
    assert payload["content"]["pdf"]["name"] == "Listino.pdf"

    bad = asyncio.run(post(_request({"type": "link", "link_url": "javascript:alert(1)"}), qr_id))
    assert bad.status_code == 303 and "err=" in bad.headers["location"]
    assert area.sql("SELECT payload FROM qr_items WHERE id=%s", (qr_id,))[0]["payload"]["type"] == "pdf"


def test_publish_refuses_invalid_content(area):
    _create(area, kind="minipage")
    qr_id = area.sql("SELECT id FROM qr_items")[0]["id"]
    refused = area.ui.link_status_post(_request(), qr_id, status="attiva")
    assert "err=" in refused.headers["location"]
    assert area.sql("SELECT status FROM qr_items")[0]["status"] == "bozza"
    asyncio.run(area.ui.link_content_post(_request({"type": "minipage", "minipage_title": "Bar Sport"}), qr_id))
    area.ui.link_status_post(_request(), qr_id, status="attiva")
    assert area.sql("SELECT status FROM qr_items")[0]["status"] == "attiva"
    with pytest.raises(HTTPException):
        area.ui.link_status_post(_request(), qr_id, status="cancellata")


def test_stats_level_is_validated(area):
    _create(area)
    qr_id = area.sql("SELECT id FROM qr_items")[0]["id"]
    area.ui.link_stats_post(_request(), qr_id, level="detailed")
    assert area.sql("SELECT stats_level FROM qr_items")[0]["stats_level"] == "detailed"
    with pytest.raises(HTTPException):
        area.ui.link_stats_post(_request(), qr_id, level="everything")


def test_other_users_cannot_open_or_edit(area):
    area.sql(
        "INSERT INTO qr_items (owner_user_id, qr_type, module, status, slug, public_path, payload) "
        "VALUES (2, 'external', 'link', 'bozza', 'OTHER123', '/d/OTHER123', '{}')"
    )
    qr_id = area.sql("SELECT id FROM qr_items")[0]["id"]
    for call in (
        lambda: area.ui.link_detail(_request(), qr_id),
        lambda: area.ui.link_stats_post(_request(), qr_id, level="none"),
        lambda: area.ui.link_qr_file(_request(), qr_id, "png"),
    ):
        with pytest.raises(HTTPException) as exc:
            call()
        assert exc.value.status_code == 403


def test_detail_page_is_labelled_and_escaped(area):
    import re

    _create(area, name='<script>alert(1)</script>')
    qr_id = area.sql("SELECT id FROM qr_items")[0]["id"]
    html = area.ui.link_detail(_request(), qr_id).body.decode()
    assert "<script>alert(1)</script>" not in html
    labels = set(re.findall(r'<label for="([^"]+)"', html))
    for control in re.findall(r'<(?:input|select|textarea)[^>]*\bid="([^"]+)"', html):
        assert control in labels, control
    assert f"/app/link/{qr_id}/qr.png" in html and f"/app/link/{qr_id}/qr.pdf" in html


def test_downloads_use_d_url(area, monkeypatch):
    _create(area)
    row = area.sql("SELECT id, slug FROM qr_items")[0]
    seen = []
    from qrfacile_app import export_qr_ui

    monkeypatch.setattr(export_qr_ui, "_qr_png", lambda url, *a: seen.append(url) or b"png")
    monkeypatch.setattr(export_qr_ui, "_qr_svg", lambda url: seen.append(url) or b"<svg/>")
    monkeypatch.setattr(export_qr_ui, "_qr_pdf_a4", lambda url, *a: seen.append(url) or b"%PDF")
    for fmt, media in (("png", "image/png"), ("svg", "image/svg+xml"), ("pdf", "application/pdf")):
        response = area.ui.link_qr_file(_request(), row["id"], fmt)
        assert response.media_type == media
    assert seen == [f"https://www.qrfacile.it/d/{row['slug']}"] * 3
    with pytest.raises(HTTPException):
        area.ui.link_qr_file(_request(), row["id"], "exe")


def test_beta_pages_redirect_only_when_on(monkeypatch):
    from qrfacile_app import external_qr_ui as ext

    monkeypatch.setattr(ext, "require_any_role", lambda *a, **k: dict(USER, role="winery"))
    monkeypatch.setattr(ext, "is_enabled", lambda key: True)
    assert ext.new_external_get(_request()).headers["location"] == "/app/link/new"
    assert ext.external_detail(_request(), 5).headers["location"] == "/app/link/5"


def test_sidebar_link_entry_follows_switch(monkeypatch):
    from qrfacile_app import ui_shell

    monkeypatch.setattr(switches, "is_enabled", lambda key: True)
    assert 'href="/app/link"' in ui_shell._sidebar("winery", "w@example.test", {"wine": 1, "generic": 0})
    monkeypatch.setattr(switches, "is_enabled", lambda key: False)
    html = ui_shell._sidebar("winery", "w@example.test", {"wine": 1, "generic": 0})
    assert 'href="/app/new-external"' in html and 'href="/app/link"' not in html
