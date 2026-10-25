from __future__ import annotations

import hashlib
import os
import secrets
import smtplib
import time
from email.message import EmailMessage
from typing import Any, Mapping

from fastapi import HTTPException
from psycopg.rows import dict_row

from qrfacile_app.db import pg

INVITE_TTL_SECONDS = 14 * 24 * 60 * 60
# The canonical service generates each raw secret with secrets.token_urlsafe(32)
# and persists only its SHA-256 digest.


def _clean_email(value: str) -> str:
    return "".join((value or "").split()).strip().lower()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _permissions(preset: str) -> tuple[bool, bool, bool]:
    value = (preset or "graphic").strip().lower()
    if value == "view":
        return True, False, False
    if value == "full":
        return True, True, True
    if value == "graphic":
        return True, True, False
    raise HTTPException(422, "Profilo permessi non valido")


def _smtp_config() -> tuple[str, int, str, str, str] | None:
    host = (os.getenv("SMTP_HOST") or "").strip()
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASS") or "").strip()
    sender = (os.getenv("SMTP_FROM") or os.getenv("FROM_EMAIL") or user).strip()
    try:
        port = int(os.getenv("SMTP_PORT") or "465")
    except ValueError:
        port = 465
    if not all((host, user, password, sender)):
        return None
    return host, port, user, password, sender


def _send_email(*, to_email: str, winery_name: str, invite_url: str) -> tuple[bool, str]:
    cfg = _smtp_config()
    if not cfg:
        return False, "SMTP non configurato"
    host, port, user, password, sender = cfg
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = f"{winery_name} ti invita a collaborare su QRFACILE"
    msg.set_content(
        f"""Buongiorno,\n\n{winery_name} ti invita a collaborare sulle proprie etichette in QRFACILE.\n\nApri il collegamento seguente per accettare o registrare lo studio:\n{invite_url}\n\nL'invito scade dopo 14 giorni e può essere revocato dalla cantina. La pubblicazione finale resta sempre alla cantina.\n\nSe non riconosci l'invito, ignoralo.\n"""
    )
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=25) as client:
                client.login(user, password)
                client.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=25) as client:
                client.starttls()
                client.login(user, password)
                client.send_message(msg)
        return True, ""
    except Exception as exc:
        return False, str(exc)[:500]


def create_invite(*, winery_id: int, actor_user_id: int, studio_email: str, preset: str, base_url: str) -> dict[str, Any]:
    """Compatibility adapter into the canonical hash-only invitations service."""
    from qrfacile_app.services.invitations import create_invitation
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id,email,role FROM users WHERE id=%s",(actor_user_id,)); actor=cur.fetchone()
            cur.execute("SELECT name FROM wineries WHERE id=%s",(winery_id,)); winery=cur.fetchone()
    if not actor or not winery: raise HTTPException(404,"Mittente o cantina non trovati")
    can_view,can_edit,can_create=_permissions(preset)
    result=create_invitation(invite_type="studio",inviter=actor,recipient_email=studio_email,
        winery_id=winery_id,permissions={"can_view":can_view,"can_edit":can_edit,"can_create":can_create})
    raw=result.pop("raw_token"); invite_url=f"{base_url.rstrip('/')}/app/invite/studio/accept/{raw}"
    sent,error=_send_email(to_email=result["invitee_email"],winery_name=str(winery["name"]),invite_url=invite_url)
    return {**result,"studio_email":result["invitee_email"],"email_sent":sent,"email_error":error,"invite_url":invite_url}


def _legacy_create_invite(*, winery_id: int, actor_user_id: int, studio_email: str, preset: str, base_url: str) -> dict[str, Any]:
    raise RuntimeError("Legacy invitation writer disabled")


def revoke_invite(*, winery_id: int, token_hash: str, actor_user_id: int) -> dict[str, Any]:
    from qrfacile_app.services.invitations import revoke_or_resend
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id FROM invites WHERE token_hash=%s AND winery_id=%s",(token_hash,winery_id)); row=cur.fetchone()
            cur.execute("SELECT id,email,role FROM users WHERE id=%s",(actor_user_id,)); actor=cur.fetchone()
    if not row or not actor: raise HTTPException(404,"Invito non trovato")
    result=revoke_or_resend(invite_id=row["id"],actor=actor)
    return {**result,"token_hash":token_hash,"studio_email":""}


def _legacy_revoke_invite(*, winery_id: int, token_hash: str, actor_user_id: int) -> dict[str, Any]:
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE studio_invites
                SET revoked_at=now(), revoked_by_user_id=%s, status='revoked'
                WHERE winery_id=%s AND token_hash=%s AND used_at IS NULL AND revoked_at IS NULL
                RETURNING token_hash, studio_email, status, revoked_at
                """,
                (int(actor_user_id), int(winery_id), token_hash),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        raise HTTPException(404, "Invito non trovato o non revocabile")
    return dict(row)


def resend_invite(*, winery_id: int, token_hash: str, base_url: str, actor_user_id: int | None = None) -> dict[str, Any]:
    from qrfacile_app.services.invitations import revoke_or_resend
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id,inviter_user_id FROM invites WHERE token_hash=%s AND winery_id=%s",(token_hash,winery_id)); row=cur.fetchone()
            uid=int(actor_user_id or (row or {}).get("inviter_user_id") or 0)
            cur.execute("SELECT id,email,role FROM users WHERE id=%s",(uid,)); actor=cur.fetchone()
            cur.execute("SELECT name FROM wineries WHERE id=%s",(winery_id,)); winery=cur.fetchone()
    if not row or not actor or not winery: raise HTTPException(404,"Invito non trovato")
    result=revoke_or_resend(invite_id=row["id"],actor=actor,resend=True)
    raw=result.pop("raw_token"); link=f"{base_url.rstrip('/')}/app/invite/{result['invite_type']}/accept/{raw}"
    sent,error=_send_email(to_email=result["invitee_email"],winery_name=winery["name"],invite_url=link)
    return {"token_hash":result["token_hash"],"email_sent":sent,"email_error":error}


def _legacy_resend_invite(*, winery_id: int, token_hash: str, base_url: str) -> dict[str, Any]:
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT si.token, si.token_hash, si.studio_email, si.expires_at, w.name AS winery_name
                FROM studio_invites si JOIN wineries w ON w.id=si.winery_id
                WHERE si.winery_id=%s AND si.token_hash=%s
                  AND si.used_at IS NULL AND si.revoked_at IS NULL
                LIMIT 1
                """,
                (int(winery_id), token_hash),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Invito non trovato o non reinviabile")
    if int(row.get("expires_at") or 0) < int(time.time()):
        raise HTTPException(409, "Invito scaduto: crearne uno nuovo")
    invite_url = f"{base_url.rstrip('/')}/app/invite/studio/accept/{row['token']}"
    sent, error = _send_email(to_email=row["studio_email"], winery_name=row["winery_name"], invite_url=invite_url)
    with pg() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE studio_invites
                SET email_delivery_status=%s, email_last_error=%s,
                    email_last_attempt_at=now(), send_attempts=send_attempts+1,
                    email_sent_at=CASE WHEN %s THEN now() ELSE email_sent_at END
                WHERE token_hash=%s
                """,
                ("sent" if sent else "failed", error or None, sent, token_hash),
            )
        conn.commit()
    return {"token_hash": token_hash, "email_sent": sent, "email_error": error}
