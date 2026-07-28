from pathlib import Path

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
