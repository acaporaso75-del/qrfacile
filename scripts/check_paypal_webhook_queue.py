#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row


def query_queue(database_url: str, *, max_age_minutes: int, connect_timeout: float) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_age_minutes)
    with psycopg.connect(
        database_url,
        row_factory=dict_row,
        connect_timeout=max(1, int(connect_timeout)),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int AS open_count,
                       COUNT(*) FILTER (
                           WHERE verification_status='failed'
                       )::int AS failed_count,
                       COUNT(*) FILTER (
                           WHERE received_at <= %s
                       )::int AS stale_count,
                       COALESCE(
                           FLOOR(EXTRACT(EPOCH FROM (now() - MIN(received_at))) / 60),
                           0
                       )::int AS oldest_age_minutes
                FROM paypal_webhook_events
                WHERE verification_status IN ('manual_review','failed')
                  AND reviewed_at IS NULL
                """,
                (cutoff,),
            )
            return dict(cur.fetchone() or {})


def evaluate_queue(row: dict, *, max_open_count: int) -> list[str]:
    reasons = []
    if int(row.get("failed_count") or 0) > 0:
        reasons.append("failed_events")
    if int(row.get("stale_count") or 0) > 0:
        reasons.append("stale_events")
    if int(row.get("open_count") or 0) > max_open_count:
        reasons.append("queue_size")
    return reasons


def _bounded_int(parser: argparse.ArgumentParser, value: int, *, name: str, low: int, high: int) -> None:
    if value < low or value > high:
        parser.error(f"{name} deve essere compreso tra {low} e {high}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Controlla la coda di revisione dei webhook PayPal senza esporre payload o ID"
    )
    parser.add_argument("--max-open-age-minutes", type=int, default=15)
    parser.add_argument("--max-open-count", type=int, default=10)
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    _bounded_int(
        parser,
        args.max_open_age_minutes,
        name="--max-open-age-minutes",
        low=1,
        high=10080,
    )
    _bounded_int(parser, args.max_open_count, name="--max-open-count", low=0, high=10000)
    if args.connect_timeout <= 0 or args.connect_timeout > 60:
        parser.error("--connect-timeout deve essere maggiore di 0 e non superiore a 60")

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        print("PAYPAL_WEBHOOK_QUEUE_ERROR DATABASE_URL non configurato", file=sys.stderr)
        return 2

    try:
        row = query_queue(
            database_url,
            max_age_minutes=args.max_open_age_minutes,
            connect_timeout=args.connect_timeout,
        )
    except psycopg.Error as exc:
        print(
            f"PAYPAL_WEBHOOK_QUEUE_ERROR database_non_verificabile={type(exc).__name__}",
            file=sys.stderr,
        )
        return 2

    counts = (
        f"open={int(row.get('open_count') or 0)} "
        f"failed={int(row.get('failed_count') or 0)} "
        f"stale={int(row.get('stale_count') or 0)} "
        f"oldest_age_minutes={int(row.get('oldest_age_minutes') or 0)}"
    )
    reasons = evaluate_queue(row, max_open_count=args.max_open_count)
    if reasons:
        print(f"PAYPAL_WEBHOOK_QUEUE_ALERT reasons={','.join(reasons)} {counts}", file=sys.stderr)
        return 1

    print(f"PAYPAL_WEBHOOK_QUEUE_OK {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
