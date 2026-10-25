"""Native PostgreSQL checks, enabled only for the explicitly configured local test DB."""
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
import pytest


@pytest.fixture
def annual_database():
    url = os.getenv("QRFACILE_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("Native PostgreSQL test DB not configured; local PGlite check is separate")
    config = conninfo_to_dict(url)
    if config.get("host") not in ("127.0.0.1", "localhost", "::1") or not config.get("dbname", "").startswith("qrfacile_test_"):
        pytest.fail("Only an explicit local test database is allowed")
    schema = "annual_test_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        try:
            conn.execute("""
                CREATE TABLE orders(id bigserial PRIMARY KEY);
                CREATE TABLE credit_ledger(
                    id bigserial PRIMARY KEY, user_id bigint NOT NULL, credit_type text NOT NULL,
                    delta integer NOT NULL, reason text, ref_table text, ref_id bigint, created_at bigint NOT NULL
                );
                CREATE VIEW available_credit_ledger AS SELECT * FROM credit_ledger;
                CREATE VIEW credit_balance AS SELECT user_id,credit_type,COALESCE(SUM(delta),0) AS balance
                FROM available_credit_ledger GROUP BY user_id,credit_type;
            """)
            migration = (Path(__file__).resolve().parents[1]/"sql/2026_annual_wine_packages.sql").read_text()
            conn.execute(migration)
            conn.execute(migration)
            yield conn, url, schema
        finally:
            conn.execute("ROLLBACK")
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_annual_expiration_preserves_used_and_legacy_balances(annual_database):
    conn, _, _ = annual_database
    conn.execute("""
        INSERT INTO credit_ledger(user_id,credit_type,delta,reason,created_at) VALUES(1,'wine',3,'legacy',1);
        INSERT INTO credit_ledger(user_id,credit_type,delta,reason,ref_table,ref_id,created_at,expires_at)
        VALUES(1,'wine',15,'annual_purchase','orders',1,1,extract(epoch FROM now())::bigint+86400);
        INSERT INTO credit_ledger(user_id,credit_type,delta,created_at) VALUES(1,'wine',-2,1);
    """)
    assert conn.execute("SELECT annual_used FROM credit_ledger WHERE ref_id=1").fetchone()[0] == 2
    assert conn.execute("SELECT balance FROM credit_balance WHERE user_id=1").fetchone()[0] == 16
    conn.execute("UPDATE credit_ledger SET expires_at=2 WHERE ref_id=1")
    assert conn.execute("SELECT balance FROM credit_balance WHERE user_id=1").fetchone()[0] == 3


def test_concurrent_spend_cannot_overdraw(annual_database):
    conn, url, schema = annual_database
    conn.execute("INSERT INTO credit_ledger(user_id,credit_type,delta,created_at) VALUES(1,'wine',1,1)")
    barrier = Barrier(2)

    def spend():
        with psycopg.connect(url, autocommit=True) as worker:
            worker.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            barrier.wait(timeout=10)
            try:
                worker.execute("INSERT INTO credit_ledger(user_id,credit_type,delta,created_at) VALUES(1,'wine',-1,1)")
                return "ok"
            except psycopg.errors.CheckViolation:
                return "insufficient"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: spend(), range(2)))
    assert sorted(results) == ["insufficient", "ok"]
    assert conn.execute("SELECT balance FROM credit_balance WHERE user_id=1").fetchone()[0] == 0
