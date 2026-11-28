from pathlib import Path
import os
from uuid import uuid4

import psycopg
import pytest
from fastapi import HTTPException
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from qrfacile_app.fiscal_profile import normalized_italian_fiscal_profile


ROOT = Path(__file__).resolve().parents[1]


def _profile(**updates):
    profile = {
        "name": "Cantina Test",
        "vat": "IT12345678903",
        "sdi": "ABC1234",
        "pec": "",
        "billing_address": "Via Test 1",
        "city": "Benevento",
        "billing_cap": "82100",
        "province": "bn",
        "billing_country": "it",
    }
    profile.update(updates)
    return profile


def test_italian_fiscal_profile_is_normalized_for_order_snapshot():
    result = normalized_italian_fiscal_profile(_profile())
    assert result == {
        "name": "Cantina Test", "vat": "12345678903", "sdi": "ABC1234", "pec": "",
        "billing_address": "Via Test 1", "city": "Benevento", "billing_cap": "82100",
        "province": "BN", "billing_country": "IT",
    }


@pytest.mark.parametrize("updates", [
    {"billing_address": ""}, {"billing_cap": "8210"}, {"province": "BNA"},
    {"billing_country": "FR"}, {"vat": "12345678901"}, {"sdi": "", "pec": "not-an-email"},
])
def test_incomplete_or_ineligible_profile_fails_closed(updates):
    with pytest.raises(HTTPException) as exc:
        normalized_italian_fiscal_profile(_profile(**updates))
    assert exc.value.status_code == 422


def test_pec_can_replace_sdi_delivery_code():
    result = normalized_italian_fiscal_profile(_profile(sdi="", pec="billing@example.test"))
    assert result["pec"] == "billing@example.test"


def test_fiscal_profile_migration_is_transactional_and_non_destructive():
    sql = (ROOT / "sql" / "2026_winery_fiscal_profile.sql").read_text(encoding="utf-8")
    assert sql.strip().startswith("BEGIN;") and sql.strip().endswith("COMMIT;")
    assert "ADD COLUMN IF NOT EXISTS billing_address" in sql
    assert "ADD COLUMN IF NOT EXISTS billing_cap" in sql
    assert "ADD COLUMN IF NOT EXISTS billing_country" in sql
    assert "DROP TABLE" not in sql.upper()


def test_authenticated_fiscal_settings_use_csrf_and_all_billing_fields():
    source = (ROOT / "qrfacile_app" / "winery_settings_ui.py").read_text(encoding="utf-8")
    assert 'action="/app/winery/settings/fiscal"' in source
    assert "require_csrf(request, csrf_token)" in source
    for field in ("billing_address", "billing_cap", "billing_country", "vat", "sdi", "pec"):
        assert f'name="{field}"' in source


def test_fiscal_profile_migration_replays_and_preserves_existing_winery():
    url = os.getenv("QRFACILE_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("Native PostgreSQL test DB not configured")
    config = conninfo_to_dict(url)
    if config.get("host") not in ("127.0.0.1", "localhost", "::1") or not config.get("dbname", "").startswith("qrfacile_test_"):
        pytest.fail("Only an explicit local test database is allowed")
    schema = "fiscal_test_" + uuid4().hex
    migration = (ROOT / "sql" / "2026_winery_fiscal_profile.sql").read_text(encoding="utf-8")
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        try:
            conn.execute("CREATE TABLE wineries(id bigserial PRIMARY KEY, name text NOT NULL)")
            conn.execute("INSERT INTO wineries(name) VALUES ('Storica')")
            conn.execute(migration)
            conn.execute(migration)
            row = conn.execute(
                "SELECT name,billing_address,billing_cap,billing_country FROM wineries"
            ).fetchone()
            assert row == ("Storica", None, None, None)
        finally:
            conn.execute("ROLLBACK")
            conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
