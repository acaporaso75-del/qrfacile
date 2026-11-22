"""Link legal addendum: first-use acceptance and public abuse reports."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from qrfacile_app import legal_core
from tests.test_link_app_area import _create, _request, area  # noqa: F401 - fixture

pytestmark = pytest.mark.integration


def test_link_legal_versions_declared():
    assert legal_core.LINK_LEGAL_DOCUMENTS == {"terms": "2026-12-link", "privacy": "2026-12-link"}


def test_first_use_requires_link_terms(area):
    area.sql("DELETE FROM legal_acceptances")
    html = area.ui.link_list(_request()).body.decode()
    assert 'action="/app/link/accept"' in html and 'id="link-accept"' in html
    blocked = area.ui.link_new_post(_request(), name="X", kind="link")
    assert blocked.headers["location"].startswith("/app/link")
    assert area.sql("SELECT COUNT(*) AS n FROM qr_items")[0]["n"] == 0

    refused = area.ui.link_accept_post(_request(), accept="")
    assert "err=" in refused.headers["location"]
    area.ui.link_accept_post(_request(), accept="yes")
    rows = area.sql("SELECT document_key, document_version, evidence FROM legal_acceptances ORDER BY document_key")
    assert [(r["document_key"], r["document_version"]) for r in rows] == [("privacy", "2026-12-link"), ("terms", "2026-12-link")]
    assert rows[0]["evidence"]["method"] == "link_first_use"
    _create(area)
    assert area.sql("SELECT COUNT(*) AS n FROM qr_items")[0]["n"] == 1


def _abuse(area, monkeypatch):
    from qrfacile_app.modules import abuse_ui
    import psycopg
    from psycopg.rows import dict_row

    url = area.url
    monkeypatch.setattr(abuse_ui, "pg", lambda: psycopg.connect(url, row_factory=dict_row))
    monkeypatch.setattr(abuse_ui, "require_any_role", lambda *a, **k: {"id": 1, "email": "a@example.test", "role": "admin"})
    monkeypatch.setattr(abuse_ui, "csrf_input", lambda request: "")
    monkeypatch.setattr(abuse_ui, "require_csrf_or_same_origin", lambda request: None)
    return abuse_ui


def test_abuse_report_rate_limited_and_honeypot(area, monkeypatch):
    ui = _abuse(area, monkeypatch)
    _create(area)
    slug = area.sql("SELECT slug FROM qr_items")[0]["slug"]
    html = ui.report_get(_request(), slug).body.decode()
    assert 'action="/segnala/' in html and 'name="website"' in html
    bot = ui.report_post(_request(), slug, reason="illegal", details="x", website="http://spam")
    assert bot.status_code == 200
    assert area.sql("SELECT COUNT(*) AS n FROM abuse_reports")[0]["n"] == 0
    for _ in range(7):
        ui.report_post(_request(), slug, reason="scam", details="<b>truffa</b>", website="")
    assert area.sql("SELECT COUNT(*) AS n FROM abuse_reports")[0]["n"] == 5
    ui.report_post(_request(), "NOPE1234", reason="scam", details="", website="")
    assert area.sql("SELECT COUNT(*) AS n FROM abuse_reports")[0]["n"] == 5
    with pytest.raises(HTTPException):
        ui.report_post(_request(), slug, reason="other-thing", details="", website="")


def test_admin_can_handle_and_unpublish(area, monkeypatch):
    ui = _abuse(area, monkeypatch)
    _create(area, kind="link")
    area.sql("UPDATE qr_items SET status='attiva'")
    slug = area.sql("SELECT slug FROM qr_items")[0]["slug"]
    ui.report_post(_request(), slug, reason="scam", details="<script>x</script>", website="")
    report_id = area.sql("SELECT id FROM abuse_reports")[0]["id"]
    html = ui.admin_reports(_request()).body.decode()
    assert slug in html and "<script>x</script>" not in html
    response = ui.admin_handle(_request(), report_id, unpublish="on")
    assert response.status_code == 303
    assert area.sql("SELECT status FROM qr_items")[0]["status"] == "sospesa"
    handled = area.sql("SELECT handled_at, handled_by FROM abuse_reports")[0]
    assert handled["handled_at"] is not None and handled["handled_by"] == 1
