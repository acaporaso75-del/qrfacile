from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.services.wine_compliance_explainability import run_explainable_wine_compliance

REPLAY_SCHEMA_VERSION = "2026.07.1"


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    raise TypeError(f"Tipo non serializzabile nel replay: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


def sha256_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def build_replay_snapshot(
    payload: Mapping[str, Any],
    *,
    actor_user_id: int | None = None,
    reason: str = "manual",
    created_at: datetime | None = None,
) -> dict[str, Any]:
    report = run_explainable_wine_compliance(payload)
    timestamp = (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    wine = payload.get("wine") or {}

    unsigned = {
        "replay_schema_version": REPLAY_SCHEMA_VERSION,
        "created_at": timestamp.isoformat(),
        "reason": str(reason or "manual"),
        "actor_user_id": int(actor_user_id) if actor_user_id else None,
        "wine_id": int(wine.get("wine_id") or wine.get("id") or 0),
        "winery_id": int(wine.get("winery_id") or 0),
        "engine_version": report.get("engine_version"),
        "catalog_version": report.get("catalog_version"),
        "knowledge_version": report.get("knowledge_version"),
        "payload": dict(payload),
        "report": report,
    }
    return {
        "replay_id": str(uuid.uuid4()),
        **unsigned,
        "content_hash": sha256_payload(unsigned),
        "hash_algorithm": "SHA-256",
    }


def verify_replay_snapshot(snapshot: Mapping[str, Any]) -> bool:
    unsigned = {
        key: value
        for key, value in snapshot.items()
        if key not in {"replay_id", "content_hash", "hash_algorithm"}
    }
    return str(snapshot.get("content_hash") or "") == sha256_payload(unsigned)


def persist_replay(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not verify_replay_snapshot(snapshot):
        raise ValueError("Replay non integro: hash del contenuto non valido")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO wine_compliance_replays (
                    replay_id, wine_id, winery_id, actor_user_id, reason,
                    replay_schema_version, engine_version, catalog_version,
                    knowledge_version, snapshot_json, content_hash, hash_algorithm,
                    score, publishable, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s::jsonb, %s, %s,
                    %s, %s, %s
                )
                RETURNING replay_id, wine_id, winery_id, actor_user_id, reason,
                          replay_schema_version, engine_version, catalog_version,
                          knowledge_version, content_hash, hash_algorithm, score,
                          publishable, created_at
                """,
                (
                    snapshot["replay_id"],
                    snapshot["wine_id"],
                    snapshot["winery_id"],
                    snapshot.get("actor_user_id"),
                    snapshot["reason"],
                    snapshot["replay_schema_version"],
                    snapshot.get("engine_version"),
                    snapshot.get("catalog_version"),
                    snapshot.get("knowledge_version"),
                    canonical_json(snapshot),
                    snapshot["content_hash"],
                    snapshot["hash_algorithm"],
                    int((snapshot.get("report") or {}).get("score") or 0),
                    bool((snapshot.get("report") or {}).get("publishable")),
                    snapshot["created_at"],
                ),
            )
            row = dict(cur.fetchone())
        conn.commit()
    return row


def create_and_persist_replay(
    payload: Mapping[str, Any],
    *,
    actor_user_id: int | None = None,
    reason: str = "manual",
) -> dict[str, Any]:
    snapshot = build_replay_snapshot(payload, actor_user_id=actor_user_id, reason=reason)
    stored = persist_replay(snapshot)
    return {**stored, "snapshot": snapshot, "integrity_valid": True}


def get_replay(replay_id: str) -> dict[str, Any] | None:
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT replay_id, wine_id, winery_id, actor_user_id, reason,
                       replay_schema_version, engine_version, catalog_version,
                       knowledge_version, snapshot_json, content_hash,
                       hash_algorithm, score, publishable, created_at
                FROM wine_compliance_replays
                WHERE replay_id=%s
                LIMIT 1
                """,
                (replay_id,),
            )
            row = cur.fetchone()
    if not row:
        return None
    item = dict(row)
    snapshot = item.pop("snapshot_json")
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)
    item["snapshot"] = snapshot
    item["integrity_valid"] = verify_replay_snapshot(snapshot)
    return item


def list_replays(wine_id: int, *, limit: int = 100) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 500))
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT replay_id, wine_id, winery_id, actor_user_id, reason,
                       replay_schema_version, engine_version, catalog_version,
                       knowledge_version, content_hash, hash_algorithm, score,
                       publishable, created_at
                FROM wine_compliance_replays
                WHERE wine_id=%s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (int(wine_id), safe_limit),
            )
            return [dict(row) for row in cur.fetchall()]


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    output: dict[str, Any] = {}
    if isinstance(value, Mapping):
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            output.update(_flatten(value[key], path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            output.update(_flatten(item, f"{prefix}[{index}]"))
    else:
        output[prefix] = value
    return output


def compare_replays(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_snapshot = left.get("snapshot") or left
    right_snapshot = right.get("snapshot") or right
    left_flat = _flatten(left_snapshot)
    right_flat = _flatten(right_snapshot)
    paths = sorted(set(left_flat) | set(right_flat))
    changes = [
        {"path": path, "before": left_flat.get(path), "after": right_flat.get(path)}
        for path in paths
        if left_flat.get(path) != right_flat.get(path)
        and path not in {"replay_id", "created_at", "content_hash"}
    ]
    return {
        "left_replay_id": left_snapshot.get("replay_id"),
        "right_replay_id": right_snapshot.get("replay_id"),
        "change_count": len(changes),
        "score_delta": int((right_snapshot.get("report") or {}).get("score") or 0)
        - int((left_snapshot.get("report") or {}).get("score") or 0),
        "publishable_changed": (left_snapshot.get("report") or {}).get("publishable")
        != (right_snapshot.get("report") or {}).get("publishable"),
        "changes": changes,
    }
