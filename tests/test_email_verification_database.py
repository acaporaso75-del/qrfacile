"""Regression: clicking the verification link must work on the real schema.

Production and staging store ``users.email_verified`` as INTEGER (0/1), as
the registration INSERTs show. Writing the boolean literal TRUE into that
column raised DatatypeMismatch and returned HTTP 500 on staging (2026-11-21).
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest

from qrfacile_app.services import email_verification


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    REPO_ROOT / "sql" / "2026_email_verification.sql",
    REPO_ROOT / "sql" / "2026_email_verification_enforcement.sql",
)


def _temporary_database_url() -> str:
    url = os.getenv("QRFACILE_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("QRFACILE_TEST_DATABASE_URL non configurata")
    parsed = urlsplit(url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("I test database possono contattare soltanto PostgreSQL locale")
    if not parsed.path.lstrip("/").startswith("qrfacile_test_"):
        pytest.fail("Il database temporaneo deve iniziare con qrfacile_test_")
    return url


@pytest.mark.integration
def test_verification_link_unlocks_account_on_integer_email_verified(monkeypatch):
    url = _temporary_database_url()
    token = secrets.token_urlsafe(32)

    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(
            """
            CREATE TABLE users (
                id bigserial PRIMARY KEY,
                email text NOT NULL UNIQUE,
                role text NOT NULL,
                email_verified integer NOT NULL DEFAULT 0
            )
            """
        )
        for migration in MIGRATIONS:
            conn.execute(migration.read_text(encoding="utf-8"))
        user_id = conn.execute(
            """
            INSERT INTO users (email, role, email_verified, email_verification_required)
            VALUES ('qa@example.test', 'winery', 0, TRUE) RETURNING id
            """
        ).fetchone()[0]
        conn.execute(
            """
            INSERT INTO email_verification_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, now() + interval '1 hour')
            """,
            (user_id, email_verification.token_hash(token)),
        )

    monkeypatch.setattr(email_verification, "pg", lambda: psycopg.connect(url))

    assert email_verification.verify_email(token) == {"user_id": user_id, "verified": True}

    with psycopg.connect(url) as conn:
        verified, verified_at = conn.execute(
            "SELECT email_verified, email_verified_at FROM users WHERE id=%s", (user_id,)
        ).fetchone()
        used_at = conn.execute(
            "SELECT used_at FROM email_verification_tokens WHERE user_id=%s", (user_id,)
        ).fetchone()[0]
    assert verified == 1
    assert verified_at is not None
    assert used_at is not None

    # The link is single-use.
    with pytest.raises(Exception) as second:
        email_verification.verify_email(token)
    assert getattr(second.value, "status_code", None) == 404
