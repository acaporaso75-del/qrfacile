#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.rows import dict_row


def query_sla_state(
    database_url: str,
    *,
    privacy_warning_days: int,
    incident_assessment_hours: int,
    connect_timeout: float,
) -> dict:
    now = datetime.now(timezone.utc)
    privacy_warning_at = now + timedelta(days=privacy_warning_days)
    incident_assessment_at = now - timedelta(hours=incident_assessment_hours)
    with psycopg.connect(
        database_url,
        row_factory=dict_row,
        connect_timeout=max(1, int(connect_timeout)),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int AS privacy_open,
                       COUNT(*) FILTER (WHERE due_at < now())::int AS privacy_overdue,
                       COUNT(*) FILTER (
                           WHERE due_at >= now() AND due_at <= %s
                       )::int AS privacy_due_soon
                FROM privacy_requests
                WHERE status NOT IN ('completed','rejected')
                """,
                (privacy_warning_at,),
            )
            privacy = dict(cur.fetchone() or {})
            cur.execute(
                """
                SELECT COUNT(*)::int AS incidents_open,
                       COUNT(*) FILTER (
                           WHERE severity IN ('high','critical')
                       )::int AS high_critical_open,
                       COUNT(*) FILTER (
                           WHERE owner_user_id IS NULL
                       )::int AS unowned_incidents,
                       COUNT(*) FILTER (
                           WHERE authority_notification_required IS TRUE
                             AND authority_notified_at IS NULL
                       )::int AS authority_notification_pending,
                       COUNT(*) FILTER (
                           WHERE data_subject_notification_required IS TRUE
                             AND data_subjects_notified_at IS NULL
                       )::int AS data_subject_notification_pending,
                       COUNT(*) FILTER (
                           WHERE personal_data_involved IS TRUE
                             AND authority_notification_required IS NULL
                             AND opened_at <= %s
                       )::int AS personal_data_assessment_overdue
                FROM compliance_incidents
                WHERE status <> 'closed'
                """,
                (incident_assessment_at,),
            )
            incidents = dict(cur.fetchone() or {})
    return {**privacy, **incidents}


def evaluate_sla_state(row: dict) -> list[str]:
    checks = (
        ("privacy_overdue", "privacy_overdue"),
        ("privacy_due_soon", "privacy_due_soon"),
        ("high_critical_open", "high_critical_incident"),
        ("unowned_incidents", "unowned_incident"),
        ("authority_notification_pending", "authority_notification_pending"),
        ("data_subject_notification_pending", "data_subject_notification_pending"),
        ("personal_data_assessment_overdue", "personal_data_assessment_overdue"),
    )
    return [reason for key, reason in checks if int(row.get(key) or 0) > 0]


def _bounded_int(parser: argparse.ArgumentParser, value: int, *, name: str, low: int, high: int) -> None:
    if value < low or value > high:
        parser.error(f"{name} deve essere compreso tra {low} e {high}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Controlla SLA privacy e incidenti usando solo conteggi aggregati"
    )
    parser.add_argument("--privacy-warning-days", type=int, default=7)
    parser.add_argument("--incident-assessment-hours", type=int, default=24)
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    _bounded_int(parser, args.privacy_warning_days, name="--privacy-warning-days", low=1, high=30)
    _bounded_int(
        parser,
        args.incident_assessment_hours,
        name="--incident-assessment-hours",
        low=1,
        high=72,
    )
    if args.connect_timeout <= 0 or args.connect_timeout > 60:
        parser.error("--connect-timeout deve essere maggiore di 0 e non superiore a 60")

    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        print("PRIVACY_SLA_ERROR DATABASE_URL non configurato", file=sys.stderr)
        return 2
    try:
        row = query_sla_state(
            database_url,
            privacy_warning_days=args.privacy_warning_days,
            incident_assessment_hours=args.incident_assessment_hours,
            connect_timeout=args.connect_timeout,
        )
    except psycopg.Error as exc:
        print(
            f"PRIVACY_SLA_ERROR database_non_verificabile={type(exc).__name__}",
            file=sys.stderr,
        )
        return 2

    fields = (
        "privacy_open",
        "privacy_overdue",
        "privacy_due_soon",
        "incidents_open",
        "high_critical_open",
        "unowned_incidents",
        "authority_notification_pending",
        "data_subject_notification_pending",
        "personal_data_assessment_overdue",
    )
    counts = " ".join(f"{field}={int(row.get(field) or 0)}" for field in fields)
    reasons = evaluate_sla_state(row)
    if reasons:
        print(f"PRIVACY_SLA_ALERT reasons={','.join(reasons)} {counts}", file=sys.stderr)
        return 1
    print(f"PRIVACY_SLA_OK {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
