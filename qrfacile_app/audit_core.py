from __future__ import annotations

import json
from typing import Any, Mapping

from fastapi import Request

from qrfacile_app.db import pg


def _client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else None


def write_audit_event(
    *,
    action: str,
    resource_type: str,
    actor: Mapping[str, Any] | None = None,
    resource_id: str | int | None = None,
    outcome: str = "success",
    request: Request | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    """Write an event using QRFacile's pre-existing audit_log schema.

    Audit logging is best-effort: a logging failure must not roll back the
    business operation that triggered it.
    """
    try:
        entity_id: int | None = None
        if resource_id is not None:
            try:
                entity_id = int(resource_id)
            except (TypeError, ValueError):
                entity_id = None

        event_meta = dict(metadata or {})
        event_meta.setdefault("outcome", outcome)
        if resource_id is not None and entity_id is None:
            event_meta.setdefault("resource_id_text", str(resource_id))
        if request:
            request_id = request.headers.get("x-request-id")
            if request_id:
                event_meta.setdefault("request_id", request_id)

        with pg() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.audit_log')")
                row = cur.fetchone()
                if not row or not row[0]:
                    return

                cur.execute(
                    """
                    INSERT INTO audit_log (
                        user_id, role, action, entity_type, entity_id,
                        ip, user_agent, meta
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        int(actor["id"]) if actor and actor.get("id") else None,
                        str(actor.get("role") or "") if actor else None,
                        action,
                        resource_type,
                        entity_id,
                        _client_ip(request),
                        request.headers.get("user-agent") if request else None,
                        json.dumps(event_meta, ensure_ascii=False),
                    ),
                )
            conn.commit()
    except Exception:
        return
