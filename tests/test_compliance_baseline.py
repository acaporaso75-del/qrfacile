from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_elabel_public_code_has_no_known_tracking_snippets():
    """Prevent accidental addition of common trackers to public e-label code."""
    root = ROOT / "qrfacile_app"
    candidates = [
        root / "public.py",
        root / "publish_routes.py",
        root / "wine_compliance_ui.py",
    ]
    forbidden = (
        "googletagmanager.com",
        "google-analytics.com",
        "connect.facebook.net",
        "facebook.com/tr",
        "hotjar.com",
        "clarity.ms",
    )

    scanned = 0
    for path in candidates:
        if not path.exists():
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for marker in forbidden:
            assert marker not in text, f"Tracking marker {marker} found in {path.name}"

    assert scanned > 0, "No public e-label modules were available for compliance scanning"


def test_ai_policy_requires_human_review():
    ui_text = (ROOT / "qrfacile_app" / "compliance_ui.py").read_text(encoding="utf-8")
    service_text = (
        ROOT / "qrfacile_app" / "services" / "compliance_service.py"
    ).read_text(encoding="utf-8")
    assert "human_review_required" in service_text
    assert "pending" in service_text
    assert "non devono essere pubblicati automaticamente" in ui_text


def test_compliance_routes_delegate_to_service_layer():
    ui_text = (ROOT / "qrfacile_app" / "compliance_ui.py").read_text(encoding="utf-8")
    service_path = ROOT / "qrfacile_app" / "services" / "compliance_service.py"
    assert service_path.exists()
    assert "get_compliance_status" in ui_text
    assert "register_ai_usage_record" in ui_text
    assert "INSERT INTO ai_usage_log" not in ui_text
    assert "SELECT to_regclass" not in ui_text


def test_ai_review_routes_delegate_to_service_layer():
    ui_text = (ROOT / "qrfacile_app" / "ai_review_ui.py").read_text(encoding="utf-8")
    service_path = ROOT / "qrfacile_app" / "services" / "ai_review_service.py"
    service_text = service_path.read_text(encoding="utf-8")

    assert service_path.exists()
    assert "list_pending_ai_reviews" in ui_text
    assert "review_ai_output_record" in ui_text
    assert "UPDATE ai_usage_log" not in ui_text
    assert "SELECT id, created_at" not in ui_text
    assert "VALID_REVIEW_DECISIONS" in service_text
    assert "human_review_status = 'pending'" in service_text


def test_security_middleware_blocks_framing_and_sniffing():
    path = ROOT / "qrfacile_app" / "security_middleware.py"
    text = path.read_text(encoding="utf-8")
    assert 'X-Frame-Options", "DENY"' in text
    assert 'X-Content-Type-Options", "nosniff"' in text
    assert "frame-ancestors 'none'" in text


def test_audit_helper_uses_existing_qrfacile_schema():
    text = (ROOT / "qrfacile_app" / "audit_core.py").read_text(encoding="utf-8")
    for column in (
        "user_id",
        "role",
        "action",
        "entity_type",
        "entity_id",
        "ip",
        "user_agent",
        "meta",
    ):
        assert column in text

    forbidden_legacy_assumptions = (
        "actor_user_id",
        "actor_role",
        "resource_type,\n                        resource_id",
        "occurred_at",
        "ip_address, metadata",
    )
    for marker in forbidden_legacy_assumptions:
        assert marker not in text


def test_migration_preserves_existing_audit_log_schema():
    text = (ROOT / "sql" / "2026_legal_ai_compliance.sql").read_text(encoding="utf-8")
    assert "to_regclass('public.audit_log') IS NULL" in text
    assert "ix_audit_action_time" in text
    assert "ix_audit_entity" in text
    assert "ix_audit_user_time" in text
    assert "occurred_at" not in text
    assert "actor_user_id" not in text
    assert "resource_type TEXT NOT NULL" not in text


def test_migration_is_idempotent_for_new_compliance_columns():
    text = (ROOT / "sql" / "2026_legal_ai_compliance.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS" in text
    assert "ADD COLUMN IF NOT EXISTS" in text
    assert "IF NOT EXISTS (" in text
    assert "uq_legal_acceptances_user_document_version" in text
