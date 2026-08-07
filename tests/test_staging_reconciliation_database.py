from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = REPO_ROOT / "sql" / "2026_staging_safety_reconciliation_v1.sql"
PRECHECK = REPO_ROOT / "sql" / "2026_staging_safety_reconciliation_v1_precheck.sql"
POSTCHECK = REPO_ROOT / "sql" / "2026_staging_safety_reconciliation_v1_postcheck.sql"
ROLLBACK = REPO_ROOT / "sql" / "2026_staging_safety_reconciliation_v1_rollback.sql"


def _temporary_database_url() -> str:
    url = os.getenv("QRFACILE_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("QRFACILE_TEST_DATABASE_URL non configurata")
    parsed = urlsplit(url)
    database = parsed.path.lstrip("/")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("I test migrazione possono contattare soltanto PostgreSQL locale")
    if not database.startswith("qrfacile_test_"):
        pytest.fail("Il database temporaneo deve iniziare con qrfacile_test_")
    return url


def _run_sql(conn, path: Path) -> None:
    conn.execute(path.read_text(encoding="utf-8"))


@pytest.mark.integration
def test_reconciliation_migration_postcheck_and_rollback_on_temporary_database():
    url = _temporary_database_url()
    now = int(time.time())

    with psycopg.connect(url, autocommit=True) as conn:
        database = conn.execute("SELECT current_database()").fetchone()[0]
        conn.execute("SELECT set_config('qrfacile.target_database', %s, false)", (database,))
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        conn.execute(
            """
            CREATE TABLE users (
                id bigserial PRIMARY KEY,
                email_verified boolean NOT NULL DEFAULT false
            );
            CREATE TABLE invites (id bigserial PRIMARY KEY);
            CREATE TABLE studio_invites (
                id bigserial PRIMARY KEY,
                token text,
                winery_id bigint,
                inviter_user_id bigint,
                studio_email text NOT NULL,
                can_view boolean NOT NULL DEFAULT true,
                can_edit boolean NOT NULL DEFAULT false,
                can_create boolean NOT NULL DEFAULT false,
                created_at bigint NOT NULL,
                expires_at bigint NOT NULL,
                used_at bigint,
                used_by_user_id bigint,
                recommended_pack text
            );
            """
        )
        for index in range(17):
            used = now - 100 if index < 2 else None
            expires = now - 10 if index < 16 else now + 3600
            conn.execute(
                """
                INSERT INTO studio_invites (
                    token, winery_id, studio_email, created_at, expires_at, used_at
                ) VALUES (NULL, 1, %s, %s, %s, %s)
                """,
                (f"legacy-{index}@example.test", now - 1000, expires, used),
            )

        _run_sql(conn, PRECHECK)
        _run_sql(conn, MIGRATION)
        _run_sql(conn, POSTCHECK)

        assert conn.execute(
            "SELECT state FROM qrfacile_schema_migrations WHERE migration_id=%s",
            ("2026_staging_safety_reconciliation_v1",),
        ).fetchone() == ("applied",)
        assert conn.execute(
            "SELECT count(*) FROM studio_invites WHERE token_hash IS NOT NULL"
        ).fetchone() == (0,)
        assert dict(
            conn.execute(
                "SELECT status, count(*) FROM studio_invites GROUP BY status"
            ).fetchall()
        ) == {"accepted": 2, "expired": 14, "pending": 1}
        assert conn.execute(
            "SELECT to_regclass('public.email_verification_tokens') IS NOT NULL"
        ).fetchone() == (True,)

        _run_sql(conn, MIGRATION)
        assert conn.execute("SELECT count(*) FROM studio_invites").fetchone() == (17,)
        assert conn.execute(
            "SELECT count(*) FROM studio_invites WHERE token_hash IS NOT NULL"
        ).fetchone() == (0,)

        _run_sql(conn, ROLLBACK)
        assert conn.execute(
            "SELECT state FROM qrfacile_schema_migrations WHERE migration_id=%s",
            ("2026_staging_safety_reconciliation_v1",),
        ).fetchone() == ("rolled_back",)
        assert conn.execute(
            """
            SELECT count(*) FROM information_schema.columns
            WHERE table_schema='public' AND table_name='studio_invites'
              AND column_name IN ('token_hash','status','email_delivery_status')
            """
        ).fetchone() == (0,)
        assert conn.execute(
            "SELECT to_regclass('public.email_verification_tokens') IS NULL"
        ).fetchone() == (True,)

        _run_sql(conn, MIGRATION)
        _run_sql(conn, POSTCHECK)
        assert conn.execute(
            "SELECT state FROM qrfacile_schema_migrations WHERE migration_id=%s",
            ("2026_staging_safety_reconciliation_v1",),
        ).fetchone() == ("applied",)
        assert dict(
            conn.execute(
                "SELECT status, count(*) FROM studio_invites GROUP BY status"
            ).fetchall()
        ) == {"accepted": 2, "expired": 14, "pending": 1}
        assert conn.execute(
            "SELECT count(*) FROM studio_invites WHERE token_hash IS NOT NULL"
        ).fetchone() == (0,)
        assert conn.execute(
            "SELECT to_regclass('public.email_verification_tokens') IS NOT NULL"
        ).fetchone() == (True,)


def test_migration_never_reconstructs_existing_tokens():
    source = MIGRATION.read_text(encoding="utf-8").lower()

    assert "update studio_invites set token_hash" not in source
    assert "where token is not null and token_hash is null" not in source
    assert "where token_hash is null" in source


def test_migration_never_reexecutes_qr_wines_repair():
    source = MIGRATION.read_text(encoding="utf-8").lower()

    assert "delete from qr_wines" not in source
    assert "qr_item_id=22" not in source.replace(" ", "")
