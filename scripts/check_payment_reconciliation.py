#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qrfacile_app.annual_packages import load_order_product


def _product_credit_checks(orders: list[dict], grants: list[dict]) -> dict[str, int]:
    by_order = {
        (int(row["ref_id"]), str(row["credit_type"])): int(row["units"] or 0)
        for row in grants
    }
    product_conditions_invalid = 0
    credit_grant_mismatch = 0
    duplicate_grant_groups = sum(1 for row in grants if int(row.get("entries") or 0) > 1)
    for order in orders:
        try:
            product = load_order_product(order)
        except Exception:
            product_conditions_invalid += 1
            continue
        expected = {
            "wine": int(product.get("wine_credits") or 0),
            "generic": int(product.get("generic_credits") or 0),
        }
        order_id = int(order["id"])
        if any(by_order.get((order_id, kind), 0) != units for kind, units in expected.items()):
            credit_grant_mismatch += 1
    return {
        "product_conditions_invalid": product_conditions_invalid,
        "credit_grant_mismatch": credit_grant_mismatch,
        "duplicate_grant_groups": duplicate_grant_groups,
    }


def query_reconciliation(database_url: str, *, connect_timeout: float) -> dict:
    with psycopg.connect(
        database_url,
        row_factory=dict_row,
        connect_timeout=max(1, int(connect_timeout)),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE status='paid' ORDER BY id")
            paid_orders = [dict(row) for row in (cur.fetchall() or [])]
            cur.execute(
                """
                SELECT ref_id, credit_type, SUM(delta)::int AS units,
                       COUNT(*)::int AS entries
                FROM credit_ledger
                WHERE ref_table='orders' AND delta > 0
                GROUP BY ref_id, credit_type
                """
            )
            grants = [dict(row) for row in (cur.fetchall() or [])]
            cur.execute(
                """
                SELECT COUNT(*) FILTER (
                           WHERE status='paid'
                             AND payment_environment IN ('live','sandbox')
                             AND COALESCE(paypal_capture_id,'')=''
                       )::int AS paid_missing_capture,
                       COUNT(*) FILTER (
                           WHERE status='paid' AND paid_at IS NULL
                       )::int AS paid_missing_timestamp,
                       COUNT(*) FILTER (
                           WHERE status='paid'
                             AND (amount_cents <= 0 OR currency <> 'EUR')
                       )::int AS paid_invalid_amount_currency,
                       COUNT(*) FILTER (
                           WHERE status='paid' AND payment_environment='unknown'
                       )::int AS unknown_environment_paid
                FROM orders
                """
            )
            state = dict(cur.fetchone() or {})
            cur.execute(
                """
                SELECT COUNT(*)::int AS duplicate_capture_groups
                FROM (
                    SELECT paypal_capture_id
                    FROM orders
                    WHERE status='paid' AND COALESCE(paypal_capture_id,'')<>''
                    GROUP BY paypal_capture_id
                    HAVING COUNT(*) > 1
                ) duplicate_captures
                """
            )
            state.update(dict(cur.fetchone() or {}))
            cur.execute(
                """
                SELECT COUNT(*) FILTER (WHERE o.id IS NULL)::int AS orphan_order_grants,
                       COUNT(*) FILTER (
                           WHERE o.id IS NOT NULL AND o.status <> 'paid'
                       )::int AS nonpaid_order_grants,
                       COUNT(*) FILTER (
                           WHERE o.id IS NOT NULL AND c.user_id <> o.user_id
                       )::int AS grant_user_mismatch
                FROM credit_ledger c
                LEFT JOIN orders o ON o.id=c.ref_id
                WHERE c.ref_table='orders' AND c.delta > 0
                """
            )
            state.update(dict(cur.fetchone() or {}))
            cur.execute(
                """
                SELECT COUNT(*)::int AS refund_review_open
                FROM paypal_webhook_events
                WHERE event_type='PAYMENT.CAPTURE.REFUNDED'
                  AND verification_status IN ('manual_review','failed')
                  AND reviewed_at IS NULL
                """
            )
            state.update(dict(cur.fetchone() or {}))
    state["paid_orders"] = len(paid_orders)
    state.update(_product_credit_checks(paid_orders, grants))
    return state


def evaluate_reconciliation(row: dict, *, max_unknown_environment_paid: int) -> list[str]:
    checks = (
        ("paid_missing_capture", "paid_missing_capture"),
        ("paid_missing_timestamp", "paid_missing_timestamp"),
        ("paid_invalid_amount_currency", "paid_invalid_amount_currency"),
        ("duplicate_capture_groups", "duplicate_capture"),
        ("orphan_order_grants", "orphan_order_grant"),
        ("nonpaid_order_grants", "nonpaid_order_grant"),
        ("grant_user_mismatch", "grant_user_mismatch"),
        ("refund_review_open", "refund_review_open"),
        ("product_conditions_invalid", "product_conditions_invalid"),
        ("credit_grant_mismatch", "credit_grant_mismatch"),
        ("duplicate_grant_groups", "duplicate_grant"),
    )
    reasons = [reason for key, reason in checks if int(row.get(key) or 0) > 0]
    if int(row.get("unknown_environment_paid") or 0) > max_unknown_environment_paid:
        reasons.append("unknown_environment_paid")
    return reasons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Riconcilia ordini, capture, crediti e rimborsi usando solo conteggi aggregati"
    )
    parser.add_argument("--max-unknown-environment-paid", type=int, default=0)
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    if args.max_unknown_environment_paid < 0:
        parser.error("--max-unknown-environment-paid non può essere negativo")
    if args.connect_timeout <= 0 or args.connect_timeout > 60:
        parser.error("--connect-timeout deve essere maggiore di 0 e non superiore a 60")

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        print("PAYMENT_RECONCILIATION_ERROR DATABASE_URL non configurato", file=sys.stderr)
        return 2
    try:
        row = query_reconciliation(database_url, connect_timeout=args.connect_timeout)
    except psycopg.Error as exc:
        print(
            f"PAYMENT_RECONCILIATION_ERROR database_non_verificabile={type(exc).__name__}",
            file=sys.stderr,
        )
        return 2

    fields = (
        "paid_orders",
        "paid_missing_capture",
        "paid_missing_timestamp",
        "paid_invalid_amount_currency",
        "unknown_environment_paid",
        "duplicate_capture_groups",
        "orphan_order_grants",
        "nonpaid_order_grants",
        "grant_user_mismatch",
        "refund_review_open",
        "product_conditions_invalid",
        "credit_grant_mismatch",
        "duplicate_grant_groups",
    )
    counts = " ".join(f"{field}={int(row.get(field) or 0)}" for field in fields)
    reasons = evaluate_reconciliation(
        row,
        max_unknown_environment_paid=args.max_unknown_environment_paid,
    )
    if reasons:
        print(f"PAYMENT_RECONCILIATION_ALERT reasons={','.join(reasons)} {counts}", file=sys.stderr)
        return 1
    print(f"PAYMENT_RECONCILIATION_OK {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
