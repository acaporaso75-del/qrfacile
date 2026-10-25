from pathlib import Path
import os
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
import pytest

from qrfacile_app import auth_routes


class _Cursor:
    def __init__(self, identity_failures=0, ip_failures=0):
        self.identity_failures = identity_failures
        self.ip_failures = ip_failures
        self.queries = []

    def execute(self, statement, params):
        query = " ".join(str(statement).split())
        self.queries.append((query, params))

    def fetchone(self):
        return {
            "identity_failures": self.identity_failures,
            "ip_failures": self.ip_failures,
        }


def test_login_limit_checks_identity_and_ip_under_transaction_locks():
    cur = _Cursor(identity_failures=auth_routes.LOGIN_IDENTITY_MAX_FAILURES)
    assert auth_routes._login_rate_limited(cur, "a" * 64, "127.0.0.1", 2_000_000_000)
    locks = [query for query, _ in cur.queries if "pg_advisory_xact_lock" in query]
    assert len(locks) == 2
    assert any("DELETE FROM login_failures WHERE created_at < %s" in query for query, _ in cur.queries)
    assert any("COUNT(*) FILTER (WHERE identity_hash=%s)" in query for query, _ in cur.queries)


def test_login_limit_allows_attempt_below_both_thresholds():
    cur = _Cursor(
        identity_failures=auth_routes.LOGIN_IDENTITY_MAX_FAILURES - 1,
        ip_failures=auth_routes.LOGIN_IP_MAX_FAILURES - 1,
    )
    assert not auth_routes._login_rate_limited(cur, "b" * 64, "127.0.0.2", 2_000_000_000)


def test_login_failure_storage_and_migration_are_privacy_minimised():
    source = Path(auth_routes.__file__).read_text(encoding="utf-8")
    migration = (Path(__file__).resolve().parents[1] / "sql" / "2026_login_rate_limit.sql").read_text(encoding="utf-8")
    rollback = (Path(__file__).resolve().parents[1] / "sql" / "2026_login_rate_limit_rollback.sql").read_text(encoding="utf-8")
    assert "identity_hash = _login_identity_hash(email)" in source
    assert "password_hash = u[\"pass_hash\"] if u else INVALID_LOGIN_HASH" in source
    assert "INSERT INTO login_failures" in source
    assert "DELETE FROM login_failures WHERE identity_hash=%s" in source
    assert "CREATE TABLE IF NOT EXISTS login_failures" in migration
    assert "email" not in migration.lower()
    assert migration.startswith("BEGIN;") and migration.rstrip().endswith("COMMIT;")
    assert "DROP TABLE IF EXISTS login_failures" in rollback
    assert rollback.startswith("BEGIN;") and rollback.rstrip().endswith("COMMIT;")


@pytest.mark.integration
def test_login_failure_migration_is_idempotent_on_local_postgres():
    url = os.getenv("QRFACILE_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("QRFACILE_TEST_DATABASE_URL non configurata")
    config = conninfo_to_dict(url)
    if config.get("host") not in ("127.0.0.1", "localhost", "::1") or not config.get("dbname", "").startswith("qrfacile_test_"):
        pytest.fail("Only an explicit local test database is allowed")

    schema = "login_limit_" + uuid4().hex
    migration = (Path(__file__).resolve().parents[1] / "sql" / "2026_login_rate_limit.sql").read_text(encoding="utf-8")
    rollback = (Path(__file__).resolve().parents[1] / "sql" / "2026_login_rate_limit_rollback.sql").read_text(encoding="utf-8")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        try:
            conn.execute(migration)
            conn.execute(migration)
            assert conn.execute("SELECT to_regclass('login_failures') IS NOT NULL").fetchone() == (True,)
            indexes = {row[0] for row in conn.execute("SELECT indexname FROM pg_indexes WHERE schemaname=%s", (schema,))}
            assert "idx_login_failures_identity_time" in indexes
            assert "idx_login_failures_ip_time" in indexes
            assert "idx_login_failures_created_at" in indexes
            conn.execute(rollback)
            assert conn.execute("SELECT to_regclass('login_failures') IS NULL").fetchone() == (True,)
            conn.execute(migration)
            assert conn.execute("SELECT to_regclass('login_failures') IS NOT NULL").fetchone() == (True,)
        finally:
            conn.execute("ROLLBACK")
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
