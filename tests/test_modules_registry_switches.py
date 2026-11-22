"""Module registry and admin on/off switches."""
from __future__ import annotations

import os
from urllib.parse import urlsplit

import psycopg
import pytest
from fastapi import HTTPException

from qrfacile_app.modules import registry, switches


def test_registry_declares_link_on_d_with_three_types():
    link = registry.MODULES["link"]
    assert link.prefix == "d"
    assert link.content_types == ("link", "pdf", "minipage")
    assert link.credit_type == "generic"
    assert {"e", "d", "r"} <= registry.RESERVED_PREFIXES


def test_is_enabled_false_when_database_unavailable(monkeypatch):
    switches.clear_cache()

    def boom():
        raise RuntimeError("database down")

    monkeypatch.setattr(switches, "pg", boom)
    assert switches.is_enabled("link") is False


def test_require_module_hides_off_module_except_admin(monkeypatch):
    monkeypatch.setattr(switches, "is_enabled", lambda key: False)
    with pytest.raises(HTTPException) as exc:
        switches.require_module("link", {"role": "winery"})
    assert exc.value.status_code == 404
    switches.require_module("link", {"role": "admin"})
    monkeypatch.setattr(switches, "is_enabled", lambda key: True)
    switches.require_module("link", {"role": "business"})


def _database_url() -> str:
    url = os.getenv("QRFACILE_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("QRFACILE_TEST_DATABASE_URL non configurata")
    parsed = urlsplit(url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not parsed.path.lstrip("/").startswith("qrfacile_test_"):
        pytest.fail("Solo database di test locali")
    return url


@pytest.mark.integration
def test_set_enabled_persists_and_audits(monkeypatch):
    url = _database_url()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(
            """
            CREATE TABLE module_switches (key text PRIMARY KEY, enabled boolean NOT NULL DEFAULT false,
              updated_by bigint, updated_at timestamptz NOT NULL DEFAULT now());
            INSERT INTO module_switches (key) VALUES ('link');
            CREATE TABLE audit_log (id bigserial PRIMARY KEY, user_id bigint, role text, action text,
              entity_type text, entity_id bigint, ip text, user_agent text, meta jsonb, created_at timestamptz);
            """
        )
    monkeypatch.setattr(switches, "pg", lambda: psycopg.connect(url))
    switches.clear_cache()
    assert switches.is_enabled("link") is False
    switches.set_enabled("link", True, user_id=1)
    assert switches.is_enabled("link") is True
    with pytest.raises(KeyError):
        switches.set_enabled("unknown", True, user_id=1)
    with psycopg.connect(url) as conn:
        assert conn.execute("SELECT count(*) FROM audit_log WHERE action='module_switch_changed'").fetchone()[0] == 1
        assert conn.execute("SELECT updated_by FROM module_switches WHERE key='link'").fetchone()[0] == 1
    switches.clear_cache()


def test_admin_modules_page_lists_switches_with_csrf_forms(monkeypatch):
    from types import SimpleNamespace
    from qrfacile_app.modules import admin_ui

    rows = [
        {"key": "link", "enabled": False, "updated_at": None, "updated_by_email": None},
        {"key": "link_sales_foreign", "enabled": True, "updated_at": "2026-11-22", "updated_by_email": "a@x.test"},
    ]
    monkeypatch.setattr(admin_ui, "require_any_role", lambda *a, **k: {"id": 1, "email": "a@x.test", "role": "admin"})
    monkeypatch.setattr(admin_ui, "_load_switches", lambda: rows)
    monkeypatch.setattr(admin_ui, "csrf_input", lambda request: '<input type="hidden" name="csrf_token" value="t">')
    html = admin_ui.modules_page(SimpleNamespace(cookies={})).body.decode()
    assert 'action="/admin/modules/link"' in html and 'name="csrf_token"' in html
    assert "QRFacile Link" in html and "Vendite estero" in html
    assert "Spento" in html and "Acceso" in html


def test_admin_toggle_requires_csrf_and_admin(monkeypatch):
    from types import SimpleNamespace
    from qrfacile_app.modules import admin_ui

    calls = []
    monkeypatch.setattr(admin_ui, "require_csrf_or_same_origin", lambda request: calls.append("csrf"))
    monkeypatch.setattr(admin_ui, "require_any_role", lambda request, roles: calls.append(tuple(roles)) or {"id": 9, "role": "admin"})
    monkeypatch.setattr(admin_ui, "set_enabled", lambda key, enabled, user_id: calls.append((key, enabled, user_id)))
    response = admin_ui.toggle_module(SimpleNamespace(cookies={}), "link", enabled="on")
    assert response.status_code == 303
    assert calls == ["csrf", ("admin",), ("link", True, 9)]
    monkeypatch.setattr(admin_ui, "set_enabled", lambda *a, **k: (_ for _ in ()).throw(KeyError("x")))
    import pytest as _pytest
    from fastapi import HTTPException as _H
    with _pytest.raises(_H):
        admin_ui.toggle_module(SimpleNamespace(cookies={}), "nope", enabled="on")
