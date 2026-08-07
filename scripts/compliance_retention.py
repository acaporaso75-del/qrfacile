#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import psycopg


DEFAULTS = {
    "audit_log_days": 730,
    "ai_usage_log_days": 730,
    "legal_acceptances_days": 3650,
    "closed_incidents_days": 3650,
}


def execute(dry_run: bool) -> dict[str, int | bool | str]:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL non configurata")

    result: dict[str, int | bool | str] = {
        "dry_run": dry_run,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
    statements = {
        "audit_log": "DELETE FROM audit_log WHERE occurred_at < now() - (%s * interval '1 day')",
        "ai_usage_log": "DELETE FROM ai_usage_log WHERE created_at < now() - (%s * interval '1 day')",
        "legal_acceptances": "DELETE FROM legal_acceptances WHERE accepted_at < now() - (%s * interval '1 day')",
        "compliance_incidents": "DELETE FROM compliance_incidents WHERE status='closed' AND closed_at < now() - (%s * interval '1 day')",
    }
    keys = {
        "audit_log": "audit_log_days",
        "ai_usage_log": "ai_usage_log_days",
        "legal_acceptances": "legal_acceptances_days",
        "compliance_incidents": "closed_incidents_days",
    }

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for table, sql in statements.items():
                cur.execute("SELECT to_regclass(%s)", (f"public.{table}",))
                exists = cur.fetchone()[0]
                if not exists:
                    result[table] = "missing"
                    continue
                cur.execute(sql, (DEFAULTS[keys[table]],))
                result[table] = cur.rowcount
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="QRFacile compliance retention")
    parser.add_argument("--apply", action="store_true", help="applica le cancellazioni; senza flag esegue rollback")
    args = parser.parse_args()
    print(json.dumps(execute(dry_run=not args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
