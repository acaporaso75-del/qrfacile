from __future__ import annotations

import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any

from fastapi import HTTPException
from psycopg.rows import dict_row

from qrfacile_app.db import pg

TOKEN_TTL_HOURS = 24
MAX_SEND_ATTEMPTS = 5
SEND_WINDOW_MINUTES = 60


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _smtp_config():
    host = (os.getenv("SMTP_HOST") or "").strip()
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASS") or "").strip()
    sender = (os.getenv("SMTP_FROM") or os.getenv("FROM_EMAIL") or user).strip()
    try:
        port = int(os.getenv("SMTP_PORT") or "465")
    except ValueError:
        port = 465
    return (host, port, user, password, sender) if all((host, user, password, sender)) else None


def _send_email(to_email: str, verification_url: str) -> tuple[bool, str]:
    cfg = _smtp_config()
    if not cfg:
        return False, "SMTP non configurato"
    host, port, user, password, sender = cfg
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_email
    msg["Subject"] = "Verifica il tuo indirizzo email QRFACILE"
    msg.set_content(
        "Conferma il tuo indirizzo email aprendo questo collegamento:\n\n"
        f"{verification_url}\n\nIl collegamento scade dopo 24 ore."
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


def create_verification(*, user_id: int, base_url: str) -> dict[str, Any]:
    token = secrets.token_urlsafe(32)
    hashed = token_hash(token)
    expires = datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT email, email_verified, verification_sent_at, verification_attempts
                   FROM users WHERE id=%s LIMIT 1 FOR UPDATE""",
                (int(user_id),),
            )
            user = cur.fetchone()
            if not user:
                raise HTTPException(404, "Utente non trovato")
            if bool(user.get("email_verified")):
                return {"already_verified": True, "email_sent": False}
            window_started = user.get("verification_sent_at")
            attempts = int(user.get("verification_attempts") or 0)
            window_open = bool(
                window_started
                and window_started >= datetime.now(timezone.utc) - timedelta(minutes=SEND_WINDOW_MINUTES)
            )
            if window_open and attempts >= MAX_SEND_ATTEMPTS:
                raise HTTPException(429, "Troppi invii di verifica: riprova tra un'ora")
            cur.execute(
                """UPDATE users
                   SET verification_sent_at=now(),
                       verification_attempts=CASE
                         WHEN verification_sent_at IS NULL
                           OR verification_sent_at < now()-(%s * interval '1 minute') THEN 1
                         ELSE verification_attempts+1
                       END
                   WHERE id=%s""",
                (SEND_WINDOW_MINUTES, int(user_id)),
            )
            cur.execute(
                "UPDATE email_verification_tokens SET revoked_at=now() WHERE user_id=%s AND used_at IS NULL AND revoked_at IS NULL",
                (int(user_id),),
            )
            cur.execute(
                """
                INSERT INTO email_verification_tokens (user_id, token_hash, expires_at, send_attempts)
                VALUES (%s,%s,%s,1)
                RETURNING id, token_hash, expires_at
                """,
                (int(user_id), hashed, expires),
            )
            row = dict(cur.fetchone())
        conn.commit()

    url = f"{base_url.rstrip('/')}/verify-email/{token}"
    sent, error = _send_email(str(user["email"]), url)
    with pg() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE email_verification_tokens
                SET sent_at=CASE WHEN %s THEN now() ELSE sent_at END, last_error=%s
                WHERE token_hash=%s
                """,
                (sent, error or None, hashed),
            )
        conn.commit()
    return {**row, "email_sent": sent, "email_error": error}


def verify_email(token: str) -> dict[str, Any]:
    hashed = token_hash((token or "").strip())
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, user_id, expires_at, used_at, revoked_at
                FROM email_verification_tokens WHERE token_hash=%s LIMIT 1 FOR UPDATE
                """,
                (hashed,),
            )
            row = cur.fetchone()
            if not row or row.get("used_at") or row.get("revoked_at"):
                raise HTTPException(404, "Collegamento non valido")
            if row["expires_at"] < datetime.now(timezone.utc):
                raise HTTPException(410, "Collegamento scaduto")
            cur.execute("UPDATE users SET email_verified=TRUE, email_verified_at=now() WHERE id=%s", (int(row["user_id"]),))
            cur.execute("UPDATE email_verification_tokens SET used_at=now() WHERE id=%s", (int(row["id"]),))
        conn.commit()
    return {"user_id": int(row["user_id"]), "verified": True}
