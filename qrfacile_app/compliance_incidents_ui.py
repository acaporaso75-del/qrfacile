from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from psycopg.rows import dict_row

from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import require_csrf_or_same_origin
from qrfacile_app.db import pg

router = APIRouter(tags=["compliance-incidents"])

SEVERITIES = {"low", "medium", "high", "critical"}
STATUSES = {"open", "investigating", "contained", "closed"}
MAX_INCIDENT_CATEGORY_LENGTH = 120
MAX_INCIDENT_SUMMARY_LENGTH = 4000
MAX_INCIDENT_EVIDENCE_BYTES = 20_000


def _incident_text(value: Any, field_name: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail=f"{field_name} obbligatorio")
    if len(text) > max_length:
        raise HTTPException(status_code=422, detail=f"{field_name}: massimo {max_length} caratteri")
    return text


def _incident_evidence(value: Any) -> str:
    evidence = value or {}
    if not isinstance(evidence, dict):
        raise HTTPException(status_code=422, detail="Le evidenze devono essere un oggetto JSON")
    try:
        encoded = json.dumps(evidence, ensure_ascii=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise HTTPException(status_code=422, detail="Evidenze JSON non valide") from exc
    if len(encoded.encode("utf-8")) > MAX_INCIDENT_EVIDENCE_BYTES:
        raise HTTPException(status_code=422, detail=f"Evidenze: massimo {MAX_INCIDENT_EVIDENCE_BYTES} byte")
    return encoded


def _optional_bool(payload: dict[str, Any], name: str) -> bool | None:
    if name not in payload or payload[name] is None:
        return None
    if not isinstance(payload[name], bool):
        raise HTTPException(status_code=422, detail=f"{name}: valore booleano non valido")
    return payload[name]


def _validated_incident_transition(
    *,
    payload: dict[str, Any],
    current: dict[str, Any],
    status: str,
) -> tuple[bool | None, bool, bool | None, bool]:
    authority_required = _optional_bool(payload, "authority_notification_required")
    subjects_required = _optional_bool(payload, "data_subject_notification_required")
    mark_authority = _optional_bool(payload, "mark_authority_notified") or False
    mark_subjects = _optional_bool(payload, "mark_data_subjects_notified") or False
    effective_authority = (
        authority_required
        if authority_required is not None
        else current.get("authority_notification_required")
    )
    effective_subjects = (
        subjects_required
        if subjects_required is not None
        else current.get("data_subject_notification_required")
    )

    if mark_authority and effective_authority is not True:
        raise HTTPException(422, "Notifica autorità non richiesta")
    if mark_subjects and effective_subjects is not True:
        raise HTTPException(422, "Notifica interessati non richiesta")
    if status == "closed" and current.get("personal_data_involved") is True:
        if effective_authority is None or effective_subjects is None:
            raise HTTPException(422, "Valutazione notifiche privacy incompleta")
        if effective_authority is True and not (
            current.get("authority_notified_at") or mark_authority
        ):
            raise HTTPException(422, "Notifica autorità richiesta ma non registrata")
        if effective_subjects is True and not (
            current.get("data_subjects_notified_at") or mark_subjects
        ):
            raise HTTPException(422, "Notifica interessati richiesta ma non registrata")
    return authority_required, mark_authority, subjects_required, mark_subjects


@router.get("/api/admin/compliance/incidents")
def list_incidents(request: Request, status: str | None = None):
    require_any_role(request, ("admin",))
    params: list[Any] = []
    where = ""
    if status:
        if status not in STATUSES:
            raise HTTPException(status_code=422, detail="Stato non valido")
        where = "WHERE status=%s"
        params.append(status)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT id, opened_at, closed_at, severity, category, status,
                       summary, personal_data_involved,
                       authority_notification_required,
                       authority_notified_at,
                       data_subject_notification_required,
                       data_subjects_notified_at,
                       owner_user_id
                FROM compliance_incidents
                {where}
                ORDER BY opened_at DESC
                LIMIT 500
                """,
                tuple(params),
            )
            rows = cur.fetchall()
    return {"ok": True, "incidents": rows, "generated_at": datetime.now(timezone.utc).isoformat()}


@router.post("/api/admin/compliance/incidents")
async def create_incident(request: Request):
    require_csrf_or_same_origin(request)
    admin = require_any_role(request, ("admin",))
    payload = await request.json()
    severity = str(payload.get("severity") or "").strip().lower()
    if severity not in SEVERITIES:
        raise HTTPException(status_code=422, detail="Gravità non valida")
    category = _incident_text(payload.get("category"), "Categoria", MAX_INCIDENT_CATEGORY_LENGTH)
    summary = _incident_text(payload.get("summary"), "Sintesi", MAX_INCIDENT_SUMMARY_LENGTH)
    evidence = _incident_evidence(payload.get("evidence"))

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO compliance_incidents (
                    severity, category, status, summary,
                    personal_data_involved, owner_user_id, evidence
                ) VALUES (%s, %s, 'open', %s, %s, %s, %s::jsonb)
                RETURNING id, opened_at, severity, category, status, summary
                """,
                (
                    severity,
                    category,
                    summary,
                    bool(payload.get("personal_data_involved", False)),
                    int(admin["id"]),
                    evidence,
                ),
            )
            row = cur.fetchone()
        conn.commit()

    write_audit_event(
        action="compliance_incident_created",
        resource_type="compliance_incident",
        resource_id=row["id"],
        actor=admin,
        request=request,
        metadata={"severity": severity, "category": category},
    )
    return {"ok": True, "incident": row}


@router.post("/api/admin/compliance/incidents/{incident_id}/status")
async def update_incident(incident_id: int, request: Request):
    require_csrf_or_same_origin(request)
    admin = require_any_role(request, ("admin",))
    payload = await request.json()
    status = str(payload.get("status") or "").strip().lower()
    if status not in STATUSES:
        raise HTTPException(status_code=422, detail="Stato non valido")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT personal_data_involved,
                       authority_notification_required, authority_notified_at,
                       data_subject_notification_required, data_subjects_notified_at
                FROM compliance_incidents
                WHERE id=%s
                FOR UPDATE
                """,
                (incident_id,),
            )
            current = cur.fetchone()
            if not current:
                raise HTTPException(status_code=404, detail="Incidente non trovato")
            (
                authority_required,
                mark_authority,
                subjects_required,
                mark_subjects,
            ) = _validated_incident_transition(
                payload=payload,
                current=dict(current),
                status=status,
            )
            cur.execute(
                """
                UPDATE compliance_incidents
                SET status=%s,
                    closed_at=CASE WHEN %s='closed' THEN now() ELSE NULL END,
                    authority_notification_required=COALESCE(%s, authority_notification_required),
                    authority_notified_at=CASE WHEN %s THEN COALESCE(authority_notified_at, now()) ELSE authority_notified_at END,
                    data_subject_notification_required=COALESCE(%s, data_subject_notification_required),
                    data_subjects_notified_at=CASE WHEN %s THEN COALESCE(data_subjects_notified_at, now()) ELSE data_subjects_notified_at END
                WHERE id=%s
                RETURNING id, severity, category, status, opened_at, closed_at
                """,
                (
                    status,
                    status,
                    authority_required,
                    mark_authority,
                    subjects_required,
                    mark_subjects,
                    incident_id,
                ),
            )
            row = cur.fetchone()
        conn.commit()

    write_audit_event(
        action="compliance_incident_status_changed",
        resource_type="compliance_incident",
        resource_id=incident_id,
        actor=admin,
        request=request,
        metadata={
            "status": status,
            "authority_notification_required": authority_required,
            "authority_notification_recorded": mark_authority,
            "data_subject_notification_required": subjects_required,
            "data_subject_notification_recorded": mark_subjects,
        },
    )
    return {"ok": True, "incident": row}
