from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_acceptance_service_uses_token_hash_and_clears_plain_token():
    text = (ROOT / "qrfacile_app" / "services" / "invitation_acceptance.py").read_text(encoding="utf-8")
    assert "hashlib.sha256" in text
    assert "WHERE si.token_hash=%s" in text
    assert "token=NULL" in text
    assert "L'invito è riservato a un altro indirizzo email" in text


def test_acceptance_ui_masks_email_and_requires_studio_account():
    text = (ROOT / "qrfacile_app" / "invitation_acceptance_ui.py").read_text(encoding="utf-8")
    assert "/app/invite/studio/accept/{token}" in text
    assert 'require_any_role(request, ("studio",))' in text
    assert "masked_email" in text
    assert "studio_invitation_accepted" in text
    assert "_same_origin" in text


def test_invitation_center_exposes_resend_and_revoke_without_plain_token():
    text = (ROOT / "qrfacile_app" / "invitation_center_ui.py").read_text(encoding="utf-8")
    assert "/app/winery/invitations" in text
    assert "/resend" in text
    assert "/revoke" in text
    assert "token_hash" in text
    assert "SELECT token," not in text


def test_acceptance_migration_is_transactional_and_rate_limited():
    text = (ROOT / "sql" / "2026_invitation_acceptance_hardening.sql").read_text(encoding="utf-8")
    assert text.startswith("BEGIN;")
    assert text.rstrip().endswith("COMMIT;")
    assert "ALTER COLUMN token DROP NOT NULL" in text
    assert "send_attempts > 10" in text
    assert "idx_studio_invites_token_hash_active" in text


def test_main_registers_acceptance_before_legacy_registration():
    text = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    acceptance = text.index('include_router_safe("qrfacile_app.invitation_acceptance_ui")')
    legacy = text.index('include_router_safe("qrfacile_app.studio_register_routes")')
    assert acceptance < legacy
    assert 'include_router_safe("qrfacile_app.invitation_center_ui")' in text
