from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.db import pg

router = APIRouter(tags=["legal-acceptance"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client else None


@router.get("/api/me/legal-status")
def my_legal_status(request: Request):
    user = require_any_role(request, ("admin", "winery", "studio"))
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT d.document_key, d.version, d.title, d.effective_at,
                       EXISTS (
                           SELECT 1 FROM legal_acceptances a
                           WHERE a.user_id=%s
                             AND a.document_key=d.document_key
                             AND a.document_version=d.version
                       ) AS accepted
                FROM legal_documents d
                WHERE d.effective_at <= now()
                  AND (d.retired_at IS NULL OR d.retired_at > now())
                ORDER BY d.document_key, d.effective_at DESC
                """,
                (int(user["id"]),),
            )
            rows = cur.fetchall()
    return {
        "ok": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "documents": rows,
        "all_required_accepted": all(bool(row["accepted"]) for row in rows) if rows else False,
    }


@router.post("/api/me/legal-acceptances")
async def accept_legal_document(request: Request):
    user = require_any_role(request, ("admin", "winery", "studio"))
    payload = await request.json()
    document_key = str(payload.get("document_key") or "").strip()
    document_version = str(payload.get("document_version") or "").strip()
    if not document_key or not document_version:
        raise HTTPException(status_code=422, detail="document_key e document_version obbligatori")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT document_key, version, title
                FROM legal_documents
                WHERE document_key=%s AND version=%s
                  AND effective_at <= now()
                  AND (retired_at IS NULL OR retired_at > now())
                LIMIT 1
                """,
                (document_key, document_version),
            )
            document = cur.fetchone()
            if not document:
                raise HTTPException(status_code=404, detail="Documento legale non attivo")

            cur.execute(
                """
                SELECT id, accepted_at
                FROM legal_acceptances
                WHERE user_id=%s AND document_key=%s AND document_version=%s
                ORDER BY accepted_at DESC LIMIT 1
                """,
                (int(user["id"]), document_key, document_version),
            )
            existing = cur.fetchone()
            if existing:
                return {"ok": True, "already_accepted": True, "acceptance": existing}

            evidence = {
                "method": "authenticated_api",
                "explicit_action": True,
                "document_title": document["title"],
            }
            cur.execute(
                """
                INSERT INTO legal_acceptances (
                    user_id, document_key, document_version,
                    ip_address, user_agent, evidence
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id, accepted_at
                """,
                (
                    int(user["id"]), document_key, document_version,
                    _client_ip(request), request.headers.get("user-agent"),
                    json.dumps(evidence, ensure_ascii=False),
                ),
            )
            acceptance = cur.fetchone()
        conn.commit()

    write_audit_event(
        action="legal_document_accepted",
        resource_type="legal_document",
        resource_id=f"{document_key}:{document_version}",
        actor=user,
        request=request,
        metadata={"acceptance_id": acceptance["id"]},
    )
    return {"ok": True, "already_accepted": False, "acceptance": acceptance}


@router.get("/api/admin/compliance/legal-acceptances")
def list_legal_acceptances(request: Request, limit: int = 100):
    require_any_role(request, ("admin",))
    safe_limit = max(1, min(int(limit), 500))
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT a.id, a.user_id, u.email, a.document_key,
                       a.document_version, a.accepted_at, a.ip_address
                FROM legal_acceptances a
                LEFT JOIN users u ON u.id=a.user_id
                ORDER BY a.accepted_at DESC
                LIMIT %s
                """,
                (safe_limit,),
            )
            rows = cur.fetchall()
    return {"ok": True, "items": rows, "limit": safe_limit}
