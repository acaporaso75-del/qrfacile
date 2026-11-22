"""Regression tests for the final review of the Link module."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from qrfacile_app.modules import switches
from tests.test_link_app_area import _create, _request, area  # noqa: F401 - fixture


def test_pricing_route_serves_the_full_page():
    from qrfacile_app import main

    def walk(routes):
        for route in routes:
            nested = getattr(route, "original_router", None)
            if nested is not None:
                yield from walk(nested.routes)
            else:
                yield route

    endpoints = {getattr(r, "path", ""): getattr(r, "endpoint", None) for r in walk(main.app.routes)}
    assert endpoints["/pricing"].__name__ == "pricing_page"


@pytest.mark.parametrize("value", ["/\\evil.com", "//evil.com", "/\\/evil.com", "https://evil.com", "/ok\r\nx"])
def test_billing_profile_next_rejects_offsite(value):
    from qrfacile_app.modules.billing_ui import _safe_next

    assert _safe_next(value) == ""
    assert _safe_next("/app/billing") == "/app/billing"


def test_switch_errors_are_cached(monkeypatch):
    calls = []

    def broken():
        calls.append(1)
        raise RuntimeError("no table")

    switches.clear_cache()
    monkeypatch.setattr(switches, "pg", broken)
    assert switches.is_enabled("link") is False
    assert switches.is_enabled("link") is False
    assert len(calls) == 1
    switches.clear_cache()


def test_missing_pdf_file_is_not_a_500(monkeypatch, tmp_path):
    from qrfacile_app.modules import public as resolver
    from qrfacile_app.modules.content_types import pdf
    from tests.test_module_public_resolver import REQUEST, _install

    monkeypatch.setattr(pdf, "get_uploads_dir", lambda: str(tmp_path))
    _install(monkeypatch, {"GONE": {"id": 7, "status": "attiva", "module": "link", "stats_level": "none",
                                    "payload": {"type": "pdf", "content": {"pdf": {"file": "modules/link/7/x.pdf"}}}}})
    assert resolver.resolve_module_qr(REQUEST, "GONE").status_code == 404


def test_business_cannot_pay_link_when_sales_off(monkeypatch):
    from tests.test_link_checkout_invoice import _install, _start

    state = _install(monkeypatch, switches={}, profile=None, role="business")
    with pytest.raises(HTTPException) as exc:
        _start()
    assert exc.value.status_code == 403
    assert not any(sql.startswith("INSERT INTO orders") for sql, _ in state["queries"])


@pytest.mark.integration
def test_owner_cannot_republish_suspended_qr(area, monkeypatch):
    from tests.test_link_legal_abuse import _abuse

    ui = _abuse(area, monkeypatch)
    _create(area)
    asyncio.run(area.ui.link_content_post(_request({"type": "link", "link_url": "https://example.com"}), 1))
    area.ui.link_status_post(_request(), 1, status="attiva")
    slug = area.sql("SELECT slug FROM qr_items")[0]["slug"]
    ui.report_post(_request(), slug, reason="scam", details="", website="")
    ui.admin_handle(_request(), area.sql("SELECT id FROM abuse_reports")[0]["id"], unpublish="on")
    assert area.sql("SELECT status FROM qr_items")[0]["status"] == "sospesa"
    response = area.ui.link_status_post(_request(), 1, status="attiva")
    assert "err=" in response.headers["location"]
    assert area.sql("SELECT status FROM qr_items")[0]["status"] == "sospesa"


def test_beta_target_update_keeps_module_content():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "qrfacile_app" / "external_qr_ui.py").read_text(encoding="utf-8")
    assert "payload=jsonb_build_object('url', %s::text)," not in source
    assert "COALESCE(payload, '{}'::jsonb) || jsonb_build_object(" in source
    assert "jsonb_build_object('link', jsonb_build_object('url', %s::text))" in source


def test_stats_write_is_time_bounded(monkeypatch):
    from qrfacile_app.modules import public as resolver
    from tests.test_module_public_resolver import REQUEST, _install

    store = _install(monkeypatch, {"AAA": {"id": 1, "status": "attiva", "module": "link", "stats_level": "counts",
                                           "payload": {"type": "link", "content": {"link": {"url": "https://example.com"}}}}})
    seen = []
    monkeypatch.setattr(resolver, "record_scan", lambda cur, **kw: seen.append(cur.sql))
    resolver.resolve_module_qr(REQUEST, "AAA")
    assert seen and "statement_timeout" in seen[0]
