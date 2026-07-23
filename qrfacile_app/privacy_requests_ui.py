from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from psycopg.rows import dict_row

from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg

router = APIRouter(tags=["privacy-requests"])

ALLOWED_TYPES = {"access", "rectification", "erasure", "restriction", "portability", "objection"}
ALLOWED_STATUS = {"open", "identity_check", "in_progress", "completed", "rejected"}


@router.post("/api/me/privacy-requests")
async def create_privacy_request(request: Request):
    user = require_any_role(request, ("admin", "winery", "studio"))
    payload: dict[str, Any] = await request.json()
    request_type = str(payload.get("request_type") or "").strip().lower()
    if request_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail="Tipo di richiesta privacy non valido")

    details = str(payload.get("details") or "").strip()
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT to_regclass('public.privacy_requests')")
            row = cur.fetchone()
            if not row or not row.get("to_regclass"):
                raise HTTPException(status_code=503, detail="Schema privacy non installato")
            cur.execute(
                """
                INSERT INTO privacy_requests (
                    user_id, request_type, status, details, submitted_at, due_at
                ) VALUES (
                    %s, %s, 'open', %s, now(), now() + interval '30 days'
                )
                RETURNING id, request_type, status, submitted_at, due_at
                """,
                (int(user["id"]), request_type, details),
            )
            created = cur.fetchone()
        conn.commit()

    write_audit_event(
        action="privacy_request_created",
        resource_type="privacy_request",
        resource_id=created["id"],
        actor=user,
        request=request,
        metadata={"request_type": request_type},
    )
    return {"ok": True, "request": created}


@router.get("/api/me/privacy-requests")
def my_privacy_requests(request: Request):
    user = require_any_role(request, ("admin", "winery", "studio"))
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, request_type, status, submitted_at, due_at, completed_at
                FROM privacy_requests
                WHERE user_id=%s
                ORDER BY submitted_at DESC
                """,
                (int(user["id"]),),
            )
            rows = cur.fetchall()
    return {"ok": True, "requests": rows}


@router.get("/api/admin/privacy-requests")
def admin_privacy_requests(request: Request, status: str | None = None):
    require_any_role(request, ("admin",))
    params: list[Any] = []
    where = ""
    if status:
        if status not in ALLOWED_STATUS:
            raise HTTPException(status_code=422, detail="Stato non valido")
        where = "WHERE pr.status=%s"
        params.append(status)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT pr.id, pr.user_id, u.email, pr.request_type, pr.status,
                       pr.submitted_at, pr.due_at, pr.completed_at, pr.details
                FROM privacy_requests pr
                LEFT JOIN users u ON u.id=pr.user_id
                {where}
                ORDER BY pr.submitted_at DESC
                LIMIT 500
                """,
                tuple(params),
            )
            rows = cur.fetchall()
    return {"ok": True, "requests": rows, "generated_at": datetime.now(timezone.utc).isoformat()}


@router.post("/api/admin/privacy-requests/{request_id}/status")
async def update_privacy_request(request_id: int, request: Request):
    admin = require_any_role(request, ("admin",))
    payload = await request.json()
    status = str(payload.get("status") or "").strip()
    if status not in ALLOWED_STATUS:
        raise HTTPException(status_code=422, detail="Stato non valido")

    resolution = str(payload.get("resolution") or "").strip()
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE privacy_requests
                SET status=%s,
                    resolution=%s,
                    handled_by_user_id=%s,
                    updated_at=now(),
                    completed_at=CASE WHEN %s IN ('completed','rejected') THEN now() ELSE completed_at END
                WHERE id=%s
                RETURNING id, user_id, request_type, status, due_at, completed_at
                """,
                (status, resolution, int(admin["id"]), status, request_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Richiesta non trovata")
        conn.commit()

    write_audit_event(
        action="privacy_request_status_changed",
        resource_type="privacy_request",
        resource_id=request_id,
        actor=admin,
        request=request,
        metadata={"status": status, "resolution": resolution[:500]},
    )
    return {"ok": True, "request": row}
