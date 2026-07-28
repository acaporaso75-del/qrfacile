from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_invitation_migration_tracks_lifecycle_and_delivery():
    text = (ROOT / "sql" / "2026_invitation_lifecycle.sql").read_text(encoding="utf-8")
    assert text.startswith("BEGIN;")
    assert text.rstrip().endswith("COMMIT;")
    for marker in (
        "token_hash",
        "email_delivery_status",
        "send_attempts",
        "revoked_at",
        "accepted_at",
        "sync_studio_invite_lifecycle",
    ):
        assert marker in text


def test_invitation_service_generates_strong_tokens_and_hashes():
    text = (ROOT / "qrfacile_app" / "services" / "invitation_management.py").read_text(encoding="utf-8")
    assert "secrets.token_urlsafe(32)" in text
    assert "hashlib.sha256" in text
    assert "INVITE_TTL_SECONDS" in text
    assert "email_delivery_status" in text
    assert "send_attempts=send_attempts+1" in text


def test_invitation_routes_are_same_origin_and_audited():
    text = (ROOT / "qrfacile_app" / "invitation_management_ui.py").read_text(encoding="utf-8")
    main = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    assert "from qrfacile_app.csrf_core import require_csrf_or_same_origin" in text
    assert text.count("require_csrf_or_same_origin(request)") >= 3
    assert "require_same_origin" not in text
    for event in (
        "studio_invitation_created",
        "studio_invitation_revoked",
        "studio_invitation_resent",
    ):
        assert event in text
    assert main.index('include_router_safe("qrfacile_app.invitation_management_ui")') < main.index('include_router_safe("qrfacile_app.winery_settings_ui")')


def test_studio_invites_never_grant_publish_permission():
    text = (ROOT / "qrfacile_app" / "services" / "invitation_management.py").read_text(encoding="utf-8")
    assert "can_publish" not in text
