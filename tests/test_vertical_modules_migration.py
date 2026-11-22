"""Base schema for vertical modules (QRFacile Link and following)."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "2026_vertical_modules_base.sql"


def _database_url() -> str:
    url = os.getenv("QRFACILE_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("QRFACILE_TEST_DATABASE_URL non configurata")
    parsed = urlsplit(url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not parsed.path.lstrip("/").startswith("qrfacile_test_"):
        pytest.fail("Solo database di test locali")
    return url


@pytest.mark.integration
def test_vertical_modules_migration_is_idempotent_and_keeps_beta_codes():
    url = _database_url()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(
            """
            CREATE TABLE users (id bigserial PRIMARY KEY, email text, role text NOT NULL);
            ALTER TABLE users ADD CONSTRAINT users_role_check
              CHECK (role IN ('admin','winery','studio','collaborator'));
            CREATE TABLE qr_items (
              id bigserial PRIMARY KEY, owner_user_id bigint, qr_type text, status text,
              slug text UNIQUE, payload jsonb
            );
            INSERT INTO users (email, role) VALUES ('a@example.test', 'winery');
            INSERT INTO qr_items (owner_user_id, qr_type, status, slug, payload)
            VALUES (1, 'external', 'attiva', 'AAA', '{"url": "https://example.com"}');
            """
        )
        sql = MIGRATION.read_text(encoding="utf-8")
        conn.execute(sql)
        conn.execute(sql)

        switches = dict(conn.execute("SELECT key, enabled FROM module_switches").fetchall())
        assert switches == {
            "link": False,
            "link_sales_it": False,
            "link_sales_foreign": False,
            "link_oss_threshold_exceeded": False,
        }
        module, level, url_top, url_content, kind = conn.execute(
            """SELECT module, stats_level, payload->>'url', payload->'content'->'link'->>'url',
                      payload->>'type' FROM qr_items WHERE slug='AAA'"""
        ).fetchone()
        assert (module, level, kind) == ("link", "none", "link")
        assert url_top == "https://example.com" and url_content == "https://example.com"

        conn.execute("INSERT INTO users (email, role) VALUES ('b@example.test', 'business')")
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("INSERT INTO users (email, role) VALUES ('c@example.test', 'xyz')")
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE qr_items SET stats_level='everything' WHERE slug='AAA'")
        for table in ("qr_scan_daily", "billing_profiles", "abuse_reports"):
            assert conn.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0] == table
        columns = [r[0] for r in conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='qr_scan_daily' ORDER BY ordinal_position"
        ).fetchall()]
        assert columns == ["qr_item_id", "day", "hour", "device", "lang", "scans"]
