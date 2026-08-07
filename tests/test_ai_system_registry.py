from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ai_system_registry_migration_is_transactional_and_guarded():
    text = (ROOT / "sql" / "2026_ai_system_registry.sql").read_text(encoding="utf-8")
    assert text.startswith("BEGIN;")
    assert text.rstrip().endswith("COMMIT;")
    assert "CREATE TABLE IF NOT EXISTS ai_system_registry" in text
    assert "ai_system_registry_status_check" in text
    assert "ai_system_registry_risk_check" in text
    assert "ai_system_registry_publish_check" in text
    assert "ai_system_registry_sensitive_data_check" in text


def test_ai_registry_service_blocks_sensitive_auto_publish():
    text = (
        ROOT / "qrfacile_app" / "services" / "ai_registry_service.py"
    ).read_text(encoding="utf-8")
    assert "SENSITIVE_USE_CASE_MARKERS" in text
    assert "La supervisione umana è obbligatoria" in text
    assert "La pubblicazione automatica è vietata" in text
    assert "risk == \"prohibited\" and status == \"approved\"" in text


def test_ai_registry_service_is_db_backed_and_idempotent():
    text = (
        ROOT / "qrfacile_app" / "services" / "ai_registry_service.py"
    ).read_text(encoding="utf-8")
    assert "INSERT INTO ai_system_registry" in text
    assert "ON CONFLICT (system_key) DO UPDATE" in text
    assert "list_ai_systems" in text
    assert "upsert_ai_system" in text


def test_compliance_status_requires_ai_system_registry():
    text = (
        ROOT / "qrfacile_app" / "services" / "compliance_service.py"
    ).read_text(encoding="utf-8")
    assert '"ai_system_registry"' in text
