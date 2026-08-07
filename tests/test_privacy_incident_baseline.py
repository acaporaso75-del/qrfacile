from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_privacy_request_workflow_is_registered():
    text = (ROOT / "qrfacile_app" / "privacy_requests_ui.py").read_text(encoding="utf-8")
    assert "/api/me/privacy-requests" in text
    assert "now() + interval '30 days'" in text
    assert "privacy_request_created" in text


def test_incident_register_has_notification_fields():
    text = (ROOT / "qrfacile_app" / "compliance_incidents_ui.py").read_text(encoding="utf-8")
    assert "authority_notification_required" in text
    assert "data_subject_notification_required" in text
    assert "compliance_incident_created" in text


def test_privacy_schema_has_due_date_and_constraints():
    text = (ROOT / "sql" / "2026_privacy_requests.sql").read_text(encoding="utf-8")
    assert "due_at TIMESTAMPTZ NOT NULL" in text
    assert "request_type IN" in text
    assert "status IN" in text


def test_main_registers_new_compliance_routers():
    text = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    assert 'include_router_safe("qrfacile_app.privacy_requests_ui")' in text
    assert 'include_router_safe("qrfacile_app.compliance_incidents_ui")' in text
