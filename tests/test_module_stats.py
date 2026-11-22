"""Scan statistics: aggregated counters only, never personal data."""
from __future__ import annotations

from datetime import datetime, timezone

import psycopg
import pytest

from qrfacile_app.modules import stats
from tests.test_vertical_modules_migration import MIGRATION, _database_url

IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36"
IPAD = "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
WINDOWS = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def test_device_and_language_normalization():
    assert stats.device_category(IPHONE) == "iphone"
    assert stats.device_category(ANDROID) == "android"
    assert stats.device_category(IPAD) == "tablet"
    assert stats.device_category(WINDOWS) == "computer"
    assert stats.device_category("") == "other"
    assert stats.primary_language("it-IT,it;q=0.9,en;q=0.8") == "it"
    assert stats.primary_language("") == ""
    assert stats.primary_language("<script>") == ""


class _FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, *args, **kwargs):
        self.calls.append(args)


def test_none_level_writes_nothing():
    cur = _FakeCursor()
    stats.record_scan(cur, qr_item_id=1, level="none", user_agent=IPHONE,
                      accept_language="it", now=datetime.now(timezone.utc))
    assert cur.calls == []


@pytest.fixture()
def conn():
    url = _database_url()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(
            """
            CREATE TABLE users (id bigserial PRIMARY KEY, email text, role text NOT NULL);
            CREATE TABLE qr_items (id bigserial PRIMARY KEY, owner_user_id bigint, qr_type text,
              status text, slug text UNIQUE, payload jsonb);
            INSERT INTO qr_items (qr_type, status, slug, payload) VALUES ('link','attiva','S1','{}');
            """
        )
        conn.execute(MIGRATION.read_text(encoding="utf-8"))
        yield conn


@pytest.mark.integration
def test_detailed_level_aggregates_without_personal_data(conn):
    now = datetime(2026, 11, 22, 10, 15, tzinfo=timezone.utc)
    with conn.cursor() as cur:
        for _ in range(100):
            stats.record_scan(cur, qr_item_id=1, level="detailed", user_agent=IPHONE,
                              accept_language="it-IT,it;q=0.9", now=now)
    rows = conn.execute("SELECT qr_item_id, day::text, hour, device, lang, scans FROM qr_scan_daily").fetchall()
    assert rows == [(1, "2026-11-22", 10, "iphone", "it", 100)]
    columns = [r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name='qr_scan_daily' ORDER BY ordinal_position"
    ).fetchall()]
    assert columns == ["qr_item_id", "day", "hour", "device", "lang", "scans"]
    with conn.cursor() as cur:
        result = stats.summary(cur, qr_item_id=1, days=30)
    assert result["total"] == 100
    assert result["by_device"] == [("iphone", 100)]
    assert result["by_lang"] == [("it", 100)]
    assert result["by_hour"] == [(10, 100)]


@pytest.mark.integration
def test_summary_counts_level(conn):
    day1 = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)
    day2 = datetime(2026, 11, 21, 18, tzinfo=timezone.utc)
    with conn.cursor() as cur:
        for when, times in ((day1, 3), (day2, 5)):
            for _ in range(times):
                stats.record_scan(cur, qr_item_id=1, level="counts", user_agent=WINDOWS,
                                  accept_language="en", now=when)
        result = stats.summary(cur, qr_item_id=1, days=30, today=day2.date())
    assert result["total"] == 8
    assert [(d.isoformat(), n) for d, n in result["by_day"]] == [("2026-11-20", 3), ("2026-11-21", 5)]
    assert result["by_device"] == [] and result["by_lang"] == [] and result["by_hour"] == []
