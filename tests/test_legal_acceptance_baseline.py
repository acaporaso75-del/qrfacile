from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legal_acceptance_api_requires_authenticated_roles():
    text = (ROOT / "qrfacile_app" / "legal_acceptance_ui.py").read_text(encoding="utf-8")
    assert 'require_any_role(request, ("admin", "winery", "studio"))' in text
    assert "/api/me/legal-acceptances" in text
    assert "explicit_action" in text


def test_legal_acceptance_is_version_specific_and_audited():
    text = (ROOT / "qrfacile_app" / "legal_acceptance_ui.py").read_text(encoding="utf-8")
    assert "document_version" in text
    assert "legal_document_accepted" in text
    assert "write_audit_event" in text


def test_database_prevents_duplicate_acceptance_evidence():
    text = (ROOT / "sql" / "2026_legal_acceptance_constraints.sql").read_text(encoding="utf-8")
    assert "CREATE UNIQUE INDEX" in text
    assert "user_id, document_key, document_version" in text


def test_main_registers_legal_acceptance_router():
    text = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    assert 'include_router_safe("qrfacile_app.legal_acceptance_ui")' in text
