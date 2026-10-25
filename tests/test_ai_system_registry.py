from pathlib import Path

import pytest
from fastapi import HTTPException

from qrfacile_app.services.ai_registry_service import _validate_registry_payload


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


def _valid_payload(**overrides):
    payload = {
        "system_key": "ingredient_assistant",
        "name": "Assistente ingredienti",
        "description": "Supporto redazionale",
        "provider": "internal",
        "model": "review-only",
        "intended_purpose": "Bozza ingredienti con revisione umana",
        "human_oversight_procedure": "Revisione obbligatoria prima dell'uso",
        "risk_classification": "limited",
        "status": "assessment",
    }
    payload.update(overrides)
    return payload


def test_ai_registry_fails_closed_on_unreviewed_approval_and_auto_publish():
    for payload in (
        _valid_payload(status="approved"),
        _valid_payload(auto_publish_allowed=True),
    ):
        with pytest.raises(HTTPException) as exc:
            _validate_registry_payload(payload)
        assert exc.value.status_code == 422


def test_personal_and_special_category_data_require_retention_and_dpa():
    with pytest.raises(HTTPException):
        _validate_registry_payload(_valid_payload(contains_personal_data=True))
    with pytest.raises(HTTPException):
        _validate_registry_payload(_valid_payload(
            contains_personal_data=True,
            special_category_data_allowed=True,
            retention_days=30,
            dpa_verified=False,
        ))
    _validate_registry_payload(_valid_payload(
        contains_personal_data=True,
        special_category_data_allowed=True,
        retention_days=30,
        dpa_verified=True,
    ))


def test_ai_registry_bounds_identifier_and_retention():
    with pytest.raises(HTTPException):
        _validate_registry_payload(_valid_payload(system_key="Bad key with spaces"))
    with pytest.raises(HTTPException):
        _validate_registry_payload(_valid_payload(retention_days=3651))
