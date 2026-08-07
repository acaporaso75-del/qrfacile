from __future__ import annotations

from typing import Any, Mapping

from fastapi import HTTPException
from psycopg.rows import dict_row

from qrfacile_app.db import pg

VALID_STATUSES = {"draft", "assessment", "approved", "suspended", "retired"}
VALID_RISK_CLASSIFICATIONS = {"minimal", "limited", "high", "prohibited"}
SENSITIVE_USE_CASE_MARKERS = {
    "ingredient",
    "allergen",
    "nutrition",
    "nutritional",
    "health_claim",
    "label_compliance",
    "legal_compliance",
}


def _table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) AS name", (f"public.{table_name}",))
    row = cur.fetchone() or {}
    return bool(row.get("name"))


def _validate_registry_payload(payload: Mapping[str, Any]) -> None:
    required = (
        "system_key",
        "name",
        "description",
        "provider",
        "model",
        "intended_purpose",
        "human_oversight_procedure",
    )
    missing = [name for name in required if not str(payload.get(name) or "").strip()]
    if missing:
        raise HTTPException(status_code=422, detail=f"Campi mancanti: {', '.join(missing)}")

    risk = str(payload.get("risk_classification") or "limited")
    status = str(payload.get("status") or "draft")
    if risk not in VALID_RISK_CLASSIFICATIONS:
        raise HTTPException(status_code=422, detail="Classificazione rischio AI non valida")
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail="Stato sistema AI non valido")
    if risk == "prohibited" and status == "approved":
        raise HTTPException(status_code=422, detail="Un caso d'uso proibito non può essere approvato")

    purpose = str(payload.get("intended_purpose") or "").lower()
    sensitive = any(marker in purpose for marker in SENSITIVE_USE_CASE_MARKERS)
    if sensitive and not bool(payload.get("human_oversight_required", True)):
        raise HTTPException(
            status_code=422,
            detail="La supervisione umana è obbligatoria per contenuti normativi sensibili",
        )
    if sensitive and bool(payload.get("auto_publish_allowed", False)):
        raise HTTPException(
            status_code=422,
            detail="La pubblicazione automatica è vietata per contenuti normativi sensibili",
        )


def list_ai_systems() -> list[dict[str, Any]]:
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if not _table_exists(cur, "ai_system_registry"):
                raise HTTPException(status_code=503, detail="Registro sistemi AI non installato")
            cur.execute(
                """
                SELECT id, system_key, name, provider, model, model_version,
                       intended_purpose, risk_classification,
                       transparency_notice_required, human_oversight_required,
                       auto_publish_allowed, dpa_verified, status,
                       approved_at, updated_at
                FROM ai_system_registry
                ORDER BY updated_at DESC, id DESC
                """
            )
            return [dict(row) for row in cur.fetchall()]


def upsert_ai_system(*, payload: Mapping[str, Any], actor_user_id: int | None) -> dict[str, Any]:
    _validate_registry_payload(payload)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if not _table_exists(cur, "ai_system_registry"):
                raise HTTPException(status_code=503, detail="Registro sistemi AI non installato")

            cur.execute(
                """
                INSERT INTO ai_system_registry (
                    system_key, name, description, provider, model, model_version,
                    intended_purpose, prohibited_uses, affected_users,
                    input_data_categories, output_categories,
                    contains_personal_data, special_category_data_allowed,
                    risk_classification, transparency_notice_required,
                    human_oversight_required, human_oversight_procedure,
                    auto_publish_allowed, training_data_reuse_allowed,
                    retention_days, dpa_verified, transfer_mechanism,
                    status, owner_user_id, metadata, updated_at
                ) VALUES (
                    %(system_key)s, %(name)s, %(description)s, %(provider)s,
                    %(model)s, %(model_version)s, %(intended_purpose)s,
                    %(prohibited_uses)s, %(affected_users)s,
                    %(input_data_categories)s::jsonb, %(output_categories)s::jsonb,
                    %(contains_personal_data)s, %(special_category_data_allowed)s,
                    %(risk_classification)s, %(transparency_notice_required)s,
                    %(human_oversight_required)s, %(human_oversight_procedure)s,
                    %(auto_publish_allowed)s, %(training_data_reuse_allowed)s,
                    %(retention_days)s, %(dpa_verified)s, %(transfer_mechanism)s,
                    %(status)s, %(owner_user_id)s, %(metadata)s::jsonb, now()
                )
                ON CONFLICT (system_key) DO UPDATE SET
                    name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    provider = EXCLUDED.provider,
                    model = EXCLUDED.model,
                    model_version = EXCLUDED.model_version,
                    intended_purpose = EXCLUDED.intended_purpose,
                    prohibited_uses = EXCLUDED.prohibited_uses,
                    affected_users = EXCLUDED.affected_users,
                    input_data_categories = EXCLUDED.input_data_categories,
                    output_categories = EXCLUDED.output_categories,
                    contains_personal_data = EXCLUDED.contains_personal_data,
                    special_category_data_allowed = EXCLUDED.special_category_data_allowed,
                    risk_classification = EXCLUDED.risk_classification,
                    transparency_notice_required = EXCLUDED.transparency_notice_required,
                    human_oversight_required = EXCLUDED.human_oversight_required,
                    human_oversight_procedure = EXCLUDED.human_oversight_procedure,
                    auto_publish_allowed = EXCLUDED.auto_publish_allowed,
                    training_data_reuse_allowed = EXCLUDED.training_data_reuse_allowed,
                    retention_days = EXCLUDED.retention_days,
                    dpa_verified = EXCLUDED.dpa_verified,
                    transfer_mechanism = EXCLUDED.transfer_mechanism,
                    status = EXCLUDED.status,
                    owner_user_id = EXCLUDED.owner_user_id,
                    metadata = EXCLUDED.metadata,
                    updated_at = now()
                RETURNING *
                """,
                {
                    "system_key": str(payload["system_key"]).strip(),
                    "name": str(payload["name"]).strip(),
                    "description": str(payload["description"]).strip(),
                    "provider": str(payload["provider"]).strip(),
                    "model": str(payload["model"]).strip(),
                    "model_version": payload.get("model_version"),
                    "intended_purpose": str(payload["intended_purpose"]).strip(),
                    "prohibited_uses": str(payload.get("prohibited_uses") or "").strip(),
                    "affected_users": str(payload.get("affected_users") or "").strip(),
                    "input_data_categories": payload.get("input_data_categories") or [],
                    "output_categories": payload.get("output_categories") or [],
                    "contains_personal_data": bool(payload.get("contains_personal_data", False)),
                    "special_category_data_allowed": bool(payload.get("special_category_data_allowed", False)),
                    "risk_classification": str(payload.get("risk_classification") or "limited"),
                    "transparency_notice_required": bool(payload.get("transparency_notice_required", True)),
                    "human_oversight_required": bool(payload.get("human_oversight_required", True)),
                    "human_oversight_procedure": str(payload["human_oversight_procedure"]).strip(),
                    "auto_publish_allowed": bool(payload.get("auto_publish_allowed", False)),
                    "training_data_reuse_allowed": bool(payload.get("training_data_reuse_allowed", False)),
                    "retention_days": payload.get("retention_days"),
                    "dpa_verified": bool(payload.get("dpa_verified", False)),
                    "transfer_mechanism": payload.get("transfer_mechanism"),
                    "status": str(payload.get("status") or "draft"),
                    "owner_user_id": actor_user_id,
                    "metadata": payload.get("metadata") or {},
                },
            )
            row = cur.fetchone()
        conn.commit()

    return dict(row or {})
