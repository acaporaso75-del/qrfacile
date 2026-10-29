from pathlib import Path

import pytest
from fastapi import HTTPException

from qrfacile_app.privacy_requests_ui import (
    MAX_PRIVACY_TEXT_LENGTH,
    _bounded_text,
    _validate_terminal_resolution,
)
from qrfacile_app.compliance_incidents_ui import (
    MAX_INCIDENT_CATEGORY_LENGTH,
    MAX_INCIDENT_EVIDENCE_BYTES,
    _incident_evidence,
    _incident_text,
    _validated_incident_transition,
)

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


def test_privacy_request_text_is_bounded_server_side():
    assert _bounded_text(" richiesta ", "Dettagli") == "richiesta"
    with pytest.raises(HTTPException) as exc:
        _bounded_text("x" * (MAX_PRIVACY_TEXT_LENGTH + 1), "Dettagli")
    assert exc.value.status_code == 422


def test_users_receive_resolution_and_reopened_requests_clear_completion():
    text = (ROOT / "qrfacile_app" / "privacy_requests_ui.py").read_text(encoding="utf-8")
    assert "completed_at, resolution" in text
    assert "THEN now() ELSE NULL END" in text
    assert '"resolution_recorded": bool(resolution)' in text
    assert '"resolution": resolution[:500]' not in text


def test_incident_text_and_evidence_are_bounded():
    assert _incident_text(" security ", "Categoria", MAX_INCIDENT_CATEGORY_LENGTH) == "security"
    assert _incident_evidence({"timeline": ["opened"]}) == '{"timeline": ["opened"]}'
    with pytest.raises(HTTPException):
        _incident_text("x" * (MAX_INCIDENT_CATEGORY_LENGTH + 1), "Categoria", MAX_INCIDENT_CATEGORY_LENGTH)
    with pytest.raises(HTTPException):
        _incident_evidence(["not", "an", "object"])
    with pytest.raises(HTTPException):
        _incident_evidence({"blob": "x" * MAX_INCIDENT_EVIDENCE_BYTES})


def test_reopened_incident_clears_old_closed_timestamp():
    text = (ROOT / "qrfacile_app" / "compliance_incidents_ui.py").read_text(encoding="utf-8")
    assert "closed_at=CASE WHEN %s='closed' THEN now() ELSE NULL END" in text
    assert '"authority_notification_recorded": mark_authority' in text
    assert '"data_subject_notification_recorded": mark_subjects' in text


def test_terminal_privacy_request_requires_resolution():
    _validate_terminal_resolution("in_progress", "")
    _validate_terminal_resolution("completed", "Consegna verificata")
    with pytest.raises(HTTPException, match="Risoluzione obbligatoria"):
        _validate_terminal_resolution("rejected", "")


def test_personal_data_incident_cannot_close_before_notification_assessment():
    current = {
        "personal_data_involved": True,
        "authority_notification_required": None,
        "authority_notified_at": None,
        "data_subject_notification_required": None,
        "data_subjects_notified_at": None,
    }
    with pytest.raises(HTTPException, match="Valutazione notifiche privacy incompleta"):
        _validated_incident_transition(payload={}, current=current, status="closed")

    transition = _validated_incident_transition(
        payload={
            "authority_notification_required": False,
            "data_subject_notification_required": False,
        },
        current=current,
        status="closed",
    )
    assert transition == (False, False, False, False)


def test_required_incident_notifications_must_be_registered_before_closure():
    current = {
        "personal_data_involved": True,
        "authority_notification_required": True,
        "authority_notified_at": None,
        "data_subject_notification_required": True,
        "data_subjects_notified_at": None,
    }
    with pytest.raises(HTTPException, match="Notifica autorità richiesta"):
        _validated_incident_transition(payload={}, current=current, status="closed")

    transition = _validated_incident_transition(
        payload={
            "mark_authority_notified": True,
            "mark_data_subjects_notified": True,
        },
        current=current,
        status="closed",
    )
    assert transition == (None, True, None, True)


def test_notification_markers_are_strict_booleans_and_cannot_invent_requirement():
    current = {
        "personal_data_involved": False,
        "authority_notification_required": False,
        "authority_notified_at": None,
        "data_subject_notification_required": False,
        "data_subjects_notified_at": None,
    }
    with pytest.raises(HTTPException, match="valore booleano non valido"):
        _validated_incident_transition(
            payload={"mark_authority_notified": "false"},
            current=current,
            status="investigating",
        )
    with pytest.raises(HTTPException, match="Notifica autorità non richiesta"):
        _validated_incident_transition(
            payload={"mark_authority_notified": True},
            current=current,
            status="investigating",
        )
