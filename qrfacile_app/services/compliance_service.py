from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from fastapi import HTTPException
from psycopg.rows import dict_row

from qrfacile_app.db import pg

AI_POLICY_VERSION = "2026-07-27"
VALID_AI_RISK_CLASSIFICATIONS = {"minimal", "limited", "high", "prohibited"}
MAX_AI_USAGE_LABEL_LENGTH = 200
MAX_AI_USAGE_VALUE_BYTES = 65_536
MAX_AI_USAGE_METADATA_BYTES = 20_000
REQUIRED_COMPLIANCE_TABLES = (
    "legal_documents",
    "legal_acceptances",
    "audit_log",
    "ai_usage_log",
    "ai_system_registry",
    "compliance_incidents",
)


def table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) AS name", (f"public.{table_name}",))
    row = cur.fetchone() or {}
    return bool(row.get("name"))


def get_compliance_status() -> dict[str, Any]:
    tables: dict[str, bool] = {}
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            for name in REQUIRED_COMPLIANCE_TABLES:
                tables[name] = table_exists(cur, name)

    return {
        "ok": all(tables.values()),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ai_policy_version": AI_POLICY_VERSION,
        "tables": tables,
        "tracking_on_elabel_pages_allowed": False,
        "human_review_required_for_ai": True,
        "ai_system_registry_required": True,
    }


def _serialized_json(value: Any, field_name: str, max_bytes: int) -> str:
    try:
        serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError, RecursionError) as exc:
        raise HTTPException(status_code=422, detail=f"{field_name}: JSON non valido") from exc
    if len(serialized.encode("utf-8")) > max_bytes:
        raise HTTPException(status_code=422, detail=f"{field_name}: dimensione massima {max_bytes} byte")
    return serialized


def _stable_sha256(value: Any, field_name: str) -> str:
    serialized = _serialized_json(value, field_name, MAX_AI_USAGE_VALUE_BYTES)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _usage_label(payload: Mapping[str, Any], field_name: str) -> str:
    value = str(payload.get(field_name) or "").strip()
    if not value:
        raise HTTPException(status_code=422, detail=f"Campo mancante: {field_name}")
    if len(value) > MAX_AI_USAGE_LABEL_LENGTH:
        raise HTTPException(status_code=422, detail=f"{field_name}: massimo {MAX_AI_USAGE_LABEL_LENGTH} caratteri")
    return value


def register_ai_usage_record(*, user_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    required = ("use_case", "provider", "model", "input", "output")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Campi mancanti: {', '.join(missing)}")

    use_case = _usage_label(payload, "use_case")
    provider = _usage_label(payload, "provider")
    model = _usage_label(payload, "model")
    risk = str(payload.get("risk_classification") or "limited").strip().lower()
    if risk not in VALID_AI_RISK_CLASSIFICATIONS:
        raise HTTPException(status_code=422, detail="Classificazione rischio AI non valida")
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=422, detail="I metadati AI devono essere un oggetto JSON")
    metadata_json = _serialized_json(metadata, "Metadati AI", MAX_AI_USAGE_METADATA_BYTES)
    input_hash = _stable_sha256(payload["input"], "Input AI")
    output_hash = _stable_sha256(payload["output"], "Output AI")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if not table_exists(cur, "ai_usage_log"):
                raise HTTPException(status_code=503, detail="Schema compliance non installato")

            cur.execute(
                """
                INSERT INTO ai_usage_log (
                    user_id, use_case, provider, model, model_version,
                    input_sha256, output_sha256, prompt_template_version,
                    risk_classification, contains_personal_data,
                    human_review_required, human_review_status, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    true, 'pending', %s::jsonb
                )
                RETURNING id, created_at, human_review_status
                """,
                (
                    user_id,
                    use_case,
                    provider,
                    model,
                    payload.get("model_version"),
                    input_hash,
                    output_hash,
                    payload.get("prompt_template_version"),
                    risk,
                    bool(payload.get("contains_personal_data", False)),
                    metadata_json,
                ),
            )
            row = cur.fetchone()
        conn.commit()

    return dict(row or {})
