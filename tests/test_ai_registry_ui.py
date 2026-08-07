from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ai_registry_ui_is_admin_only_and_service_backed():
    text = (ROOT / "qrfacile_app" / "ai_registry_ui.py").read_text(encoding="utf-8")
    main_text = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")

    assert 'prefix="/admin/compliance"' in text
    assert '@router.get("/ai-systems"' in text
    assert '@router.post("/ai-systems")' in text
    assert 'require_any_role(request, ("admin",))' in text
    assert "list_ai_systems" in text
    assert "upsert_ai_system" in text
    assert "write_audit_event" in text
    assert "INSERT INTO ai_system_registry" not in text
    assert 'include_router_safe("qrfacile_app.ai_registry_ui")' in main_text


def test_ai_registry_ui_exposes_required_controls():
    text = (ROOT / "qrfacile_app" / "ai_registry_ui.py").read_text(encoding="utf-8")

    for marker in (
        "risk_classification",
        "human_oversight_required",
        "auto_publish_allowed",
        "training_data_reuse_allowed",
        "dpa_verified",
        "transfer_mechanism",
        "retention_days",
    ):
        assert marker in text

    assert "html.escape" in text
