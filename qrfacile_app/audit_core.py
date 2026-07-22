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
    """Best-effort audit logging. Business operations must not fail if logging fails."""
    try:
        with pg() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.audit_log')")
                row = cur.fetchone()
                if not row or not row[0]:
                    return
                cur.execute(
                    """
                    INSERT INTO audit_log (
                        actor_user_id, actor_role, action, resource_type,
                        resource_id, outcome, request_id, ip_address, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        int(actor["id"]) if actor and actor.get("id") else None,
                        str(actor.get("role") or "") if actor else None,
                        action,
                        resource_type,
                        str(resource_id) if resource_id is not None else None,
                        outcome,
                        request.headers.get("x-request-id") if request else None,
                        _client_ip(request),
                        json.dumps(dict(metadata or {}), ensure_ascii=False),
                    ),
                )
            conn.commit()
    except Exception:
        return
