from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from fastapi import HTTPException
from psycopg.rows import dict_row

from qrfacile_app.db import pg

AI_POLICY_VERSION = "2026-07-27"
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


def _stable_sha256(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def register_ai_usage_record(*, user_id: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    required = ("use_case", "provider", "model", "input", "output")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Campi mancanti: {', '.join(missing)}")

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
                    str(payload["use_case"]),
                    str(payload["provider"]),
                    str(payload["model"]),
                    payload.get("model_version"),
                    _stable_sha256(payload["input"]),
                    _stable_sha256(payload["output"]),
                    payload.get("prompt_template_version"),
                    str(payload.get("risk_classification") or "limited"),
                    bool(payload.get("contains_personal_data", False)),
                    json.dumps(payload.get("metadata") or {}, ensure_ascii=False),
                ),
            )
            row = cur.fetchone()
        conn.commit()

    return dict(row or {})
