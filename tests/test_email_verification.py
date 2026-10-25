import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi import HTTPException
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from starlette.requests import Request

from qrfacile_app import auth_core

ROOT = Path(__file__).resolve().parents[1]


def test_email_verification_migration_is_transactional_and_hashed():
    text = (ROOT / "sql" / "2026_email_verification.sql").read_text(encoding="utf-8")
    assert text.startswith("BEGIN;")
    assert text.rstrip().endswith("COMMIT;")
    assert "token_hash CHAR(64)" in text
    assert "email_verified_at" in text
    assert "sync_email_verified_state" in text


def test_verification_service_uses_strong_tokens_and_sha256():
    text = (ROOT / "qrfacile_app" / "services" / "email_verification.py").read_text(encoding="utf-8")
    assert "secrets.token_urlsafe(32)" in text
    assert "hashlib.sha256" in text
    assert "TOKEN_TTL_HOURS = 24" in text
    assert "UPDATE users SET email_verified=TRUE" in text
    assert "used_at=now()" in text


def test_verification_routes_are_registered_and_audited():
    ui = (ROOT / "qrfacile_app" / "email_verification_ui.py").read_text(encoding="utf-8")
    main = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    assert '@router.get("/verify-email/{token}"' in ui
    assert '@router.post("/api/me/email-verification/resend")' in ui
    assert "require_csrf_or_same_origin" in ui
    assert "email_verified" in ui
    assert "email_verification_requested" in ui
    assert 'include_router_safe("qrfacile_app.email_verification_ui")' in main


def test_new_accounts_are_restricted_and_receive_an_initial_verification():
    auth = (ROOT / "qrfacile_app" / "auth_core.py").read_text(encoding="utf-8")
    login = (ROOT / "qrfacile_app" / "auth_routes.py").read_text(encoding="utf-8")
    ui = (ROOT / "qrfacile_app" / "email_verification_ui.py").read_text(encoding="utf-8")
    for filename in ("winery_register_routes.py", "studio_register_routes.py"):
        registration = (ROOT / "qrfacile_app" / filename).read_text(encoding="utf-8")
        assert "email_verification_required" in registration
        assert "create_verification(user_id=user_id" in registration
    assert 'headers={"Location": "/verify-email-required"}' in auth
    assert "/verify-email-required?next=" in login
    assert '@router.get("/verify-email-required"' in ui
    assert "csrf_input(request)" in ui
    assert "user = get_current_user(request)" in ui


def test_required_unverified_account_is_redirected_before_role_access(monkeypatch):
    monkeypatch.setattr(auth_core, "get_current_user", lambda _request: {
        "id": 7, "email": "new@example.test", "role": "winery",
        "email_verified": False, "email_verification_required": True,
    })
    request = Request({"type": "http", "method": "GET", "path": "/app/start", "headers": []})
    with pytest.raises(HTTPException) as exc:
        auth_core.require_any_role(request, ("winery",))
    assert exc.value.status_code == 303
    assert exc.value.headers["Location"] == "/verify-email-required"


def test_email_enforcement_migration_preserves_existing_accounts_and_defaults_new_ones():
    url = os.getenv("QRFACILE_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("Native PostgreSQL test DB not configured")
    config = conninfo_to_dict(url)
    if config.get("host") not in ("127.0.0.1", "localhost", "::1") or not config.get("dbname", "").startswith("qrfacile_test_"):
        pytest.fail("Only an explicit local test database is allowed")
    schema = "email_gate_test_" + uuid4().hex
    migration = (ROOT / "sql" / "2026_email_verification_enforcement.sql").read_text(encoding="utf-8")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        try:
            conn.execute("CREATE TABLE users(id bigserial PRIMARY KEY, email text NOT NULL)")
            conn.execute("INSERT INTO users(email) VALUES ('existing@example.test')")
            conn.execute(migration)
            conn.execute(migration)
            conn.execute("INSERT INTO users(email) VALUES ('new@example.test')")
            rows = conn.execute("SELECT email,email_verification_required FROM users ORDER BY id").fetchall()
            assert rows == [("existing@example.test", False), ("new@example.test", True)]
        finally:
            conn.execute("ROLLBACK")
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
