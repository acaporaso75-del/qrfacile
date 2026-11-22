"""Scan statistics for module QR codes.

Only aggregated counters are stored: per QR, per day and, at the
"detailed" level, per hour, device category and primary language.
No IP address, no full user agent, no cookie, no identifier.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

STATS_LEVELS = ("none", "counts", "detailed")

_UPSERT = """
INSERT INTO qr_scan_daily (qr_item_id, day, hour, device, lang, scans)
VALUES (%s, %s, %s, %s, %s, 1)
ON CONFLICT (qr_item_id, day, hour, device, lang)
DO UPDATE SET scans = qr_scan_daily.scans + 1
"""


def device_category(user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if not ua:
        return "other"
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        return "tablet"
    if "iphone" in ua or "ipod" in ua:
        return "iphone"
    if "android" in ua:
        return "android"
    if any(token in ua for token in ("windows", "macintosh", "x11", "linux", "cros")):
        return "computer"
    return "other"


def primary_language(accept_language: str) -> str:
    first = (accept_language or "").split(",", 1)[0].strip().lower()
    match = re.match(r"^([a-z]{2})(?:[-_][a-z0-9]+)*(?:;.*)?$", first)
    return match.group(1) if match else ""


def record_scan(cur, *, qr_item_id: int, level: str, user_agent: str, accept_language: str, now: datetime) -> None:
    if level not in ("counts", "detailed"):
        return
    if level == "detailed":
        key = (now.hour, device_category(user_agent), primary_language(accept_language))
    else:
        key = (-1, "", "")
    cur.execute(_UPSERT, (int(qr_item_id), now.date(), *key))


def summary(cur, *, qr_item_id: int, days: int = 30, today: date | None = None) -> dict:
    since = (today or date.today()) - timedelta(days=max(1, int(days)) - 1)
    params = (int(qr_item_id), since)
    cur.execute(
        "SELECT day, SUM(scans)::int FROM qr_scan_daily WHERE qr_item_id=%s AND day>=%s GROUP BY day ORDER BY day",
        params,
    )
    by_day = [(row[0], int(row[1])) for row in cur.fetchall()]

    def grouped(column: str, where: str) -> list[tuple]:
        cur.execute(
            f"SELECT {column}, SUM(scans)::int AS n FROM qr_scan_daily "
            f"WHERE qr_item_id=%s AND day>=%s AND {where} GROUP BY {column} ORDER BY n DESC, {column}",
            params,
        )
        return [(row[0], int(row[1])) for row in cur.fetchall()]

    by_hour = sorted(grouped("hour", "hour >= 0"))
    return {
        "total": sum(n for _, n in by_day),
        "by_day": by_day,
        "by_device": grouped("device", "device <> ''"),
        "by_lang": grouped("lang", "lang <> ''"),
        "by_hour": by_hour,
    }
