from pathlib import Path

import pytest
from fastapi import HTTPException

from qrfacile_app.services.invitations import normalize_permissions, token_hash, validate_token

ROOT = Path(__file__).resolve().parents[1]


def test_token_hash_is_deterministic_and_raw_is_not_returned():
    raw = "A" * 43
    assert len(token_hash(raw)) == 64
    assert token_hash(raw) == token_hash(raw)
    assert raw not in token_hash(raw)


@pytest.mark.parametrize("raw", ["", "short", "contains space", "../bad-token"])
def test_malformed_tokens_are_neutral_404(raw):
    with pytest.raises(HTTPException) as error:
        validate_token(raw)
    assert error.value.status_code == 404


def test_permissions_never_escalate_publish_or_delegation():
    permissions = normalize_permissions({"can_view": True, "can_edit": True, "can_publish": True, "can_delegate": True})
    assert permissions["can_edit"] is True
    assert permissions["can_publish"] is False
    assert permissions["can_delegate"] is False


def test_edit_requires_view():
    permissions = normalize_permissions({"can_view": False, "can_edit": True, "can_create": True})
    assert not any((permissions["can_view"], permissions["can_edit"], permissions["can_create"]))


def test_unified_migration_is_hash_only_transactional_and_indexed():
    sql = (ROOT / "sql" / "2026_unified_invitations.sql").read_text()
    assert sql.startswith("BEGIN;") and sql.rstrip().endswith("COMMIT;")
    assert "token_hash CHAR(64)" in sql
    assert "UPDATE invites SET legacy_token=NULL" in sql
    assert "UPDATE studio_invites SET token=NULL" in sql
    assert "uq_invites_token_hash" in sql
    assert "idx_invites_recipient_email" in sql
    assert "idx_invites_status_expiry" in sql
    for state in ("pending", "accepted", "rejected", "expired", "revoked"):
        assert state in sql


def test_acceptance_uses_lock_transaction_and_post_csrf():
    service = (ROOT / "qrfacile_app" / "services" / "invitations.py").read_text()
    ui = (ROOT / "qrfacile_app" / "invitations_ui.py").read_text()
    assert "FOR UPDATE" in service
    assert "conn.commit()" in service
    assert "invitation_grants" in service
    assert '@router.post("/app/invite/decide")' in ui
    assert "require_csrf(request,csrf_token)" in ui
    assert "can_publish\": False" in service


def test_resume_cookie_contains_only_signed_invite_id():
    ui = (ROOT / "qrfacile_app" / "invitations_ui.py").read_text()
    assert "httponly=True" in ui
    assert "samesite=\"lax\"" in ui
    assert "_resume_value(invite[\"id\"])" in ui
    assert "raw_token" not in ui.split("def _resume_value", 1)[1].split("def _resume_id", 1)[0]
