from __future__ import annotations

import hashlib
import time
from typing import Any

from fastapi import HTTPException
from psycopg.rows import dict_row

from qrfacile_app.db import pg


def token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def mask_email(email: str) -> str:
    value = (email or "").strip()
    if "@" not in value:
        return "***"
    local, domain = value.split("@", 1)
    local_masked = (local[:1] or "*") + "***"
    if "." in domain:
        host, suffix = domain.rsplit(".", 1)
        domain_masked = (host[:1] or "*") + "***." + suffix
    else:
        domain_masked = (domain[:1] or "*") + "***"
    return f"{local_masked}@{domain_masked}"


def get_invite_by_token(token: str) -> dict[str, Any]:
    digest = token_hash(token)
    now = int(time.time())
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT si.token_hash, si.winery_id, si.studio_email,
                       si.can_view, si.can_edit, si.can_create,
                       si.created_at, si.expires_at, si.used_at,
                       si.revoked_at, si.status, w.name AS winery_name
                FROM studio_invites si
                JOIN wineries w ON w.id=si.winery_id
                WHERE si.token_hash=%s
                LIMIT 1
                """,
                (digest,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Invito non trovato")
    item = dict(row)
    if item.get("revoked_at") or item.get("status") == "revoked":
        raise HTTPException(410, "Invito revocato")
    if item.get("used_at") or item.get("status") == "accepted":
        raise HTTPException(409, "Invito già utilizzato")
    if int(item.get("expires_at") or 0) < now:
        raise HTTPException(410, "Invito scaduto")
    item["masked_email"] = mask_email(str(item.get("studio_email") or ""))
    return item


def accept_invite_for_existing_studio(*, token: str, studio_user_id: int, studio_email: str) -> dict[str, Any]:
    invite = get_invite_by_token(token)
    expected = str(invite.get("studio_email") or "").strip().lower()
    actual = str(studio_email or "").strip().lower()
    if expected != actual:
        raise HTTPException(403, "L'invito è riservato a un altro indirizzo email")

    ts = int(time.time())
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO studio_clients
                    (studio_user_id, winery_id, can_view, can_edit, can_create, created_at)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (studio_user_id, winery_id)
                DO UPDATE SET
                    can_view=EXCLUDED.can_view,
                    can_edit=EXCLUDED.can_edit,
                    can_create=EXCLUDED.can_create
                """,
                (
                    int(studio_user_id), int(invite["winery_id"]),
                    bool(invite.get("can_view")), bool(invite.get("can_edit")),
                    bool(invite.get("can_create")), ts,
                ),
            )
            cur.execute(
                """
                UPDATE studio_invites
                SET used_at=%s, used_by_user_id=%s, accepted_at=now(), status='accepted', token=NULL
                WHERE token_hash=%s AND used_at IS NULL AND revoked_at IS NULL
                RETURNING token_hash, winery_id, studio_email, status, accepted_at
                """,
                (ts, int(studio_user_id), token_hash(token)),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(409, "Invito non più utilizzabile")
        conn.commit()
    return dict(row)
