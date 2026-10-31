#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


@dataclass(frozen=True)
class Check:
    name: str
    arguments: tuple[str, ...]


def build_checks(args: argparse.Namespace) -> tuple[Check, ...]:
    return (
        Check("transactional_email", (str(SCRIPTS_DIR / "check_transactional_email.py"),)),
        Check(
            "paypal_webhook_queue",
            (
                str(SCRIPTS_DIR / "check_paypal_webhook_queue.py"),
                "--max-open-age-minutes",
                str(args.max_open_age_minutes),
                "--max-open-count",
                str(args.max_open_count),
            ),
        ),
        Check(
            "privacy_sla",
            (
                str(SCRIPTS_DIR / "check_privacy_sla.py"),
                "--privacy-warning-days",
                str(args.privacy_warning_days),
                "--incident-assessment-hours",
                str(args.incident_assessment_hours),
            ),
        ),
        Check(
            "payment_reconciliation",
            (
                str(SCRIPTS_DIR / "check_payment_reconciliation.py"),
                "--max-unknown-environment-paid",
                str(args.max_unknown_environment_paid),
            ),
        ),
    )


def execute_checks(checks: tuple[Check, ...], *, timeout: float) -> dict[str, str]:
    results: dict[str, str] = {}
    for check in checks:
        try:
            completed = subprocess.run(
                [sys.executable, *check.arguments],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            results[check.name] = "error"
            continue
        results[check.name] = (
            "ok" if completed.returncode == 0 else "alert" if completed.returncode == 1 else "error"
        )
    return results


def add_check_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-open-age-minutes", type=int, default=15)
    parser.add_argument("--max-open-count", type=int, default=10)
    parser.add_argument("--privacy-warning-days", type=int, default=7)
    parser.add_argument("--incident-assessment-hours", type=int, default=24)
    parser.add_argument("--max-unknown-environment-paid", type=int, default=0)
    parser.add_argument("--timeout-per-check", type=float, default=30.0)


def validate_check_arguments(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if args.timeout_per_check <= 0 or args.timeout_per_check > 120:
        parser.error("--timeout-per-check deve essere maggiore di 0 e non superiore a 120")
    if args.max_unknown_environment_paid < 0:
        parser.error("--max-unknown-environment-paid non può essere negativo")


def result_code(results: dict[str, str]) -> int:
    if any(status == "error" for status in results.values()):
        return 2
    if any(status == "alert" for status in results.values()):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Esegue i probe operativi QRFacile senza esportarne contenuti o identificativi"
    )
    add_check_arguments(parser)
    args = parser.parse_args(argv)
    validate_check_arguments(parser, args)

    results = execute_checks(build_checks(args), timeout=args.timeout_per_check)
    for name, status in results.items():
        print(f"OPERATIONAL_CHECK name={name} status={status}")

    errors = sorted(name for name, status in results.items() if status == "error")
    alerts = sorted(name for name, status in results.items() if status == "alert")
    outcome = result_code(results)
    if outcome == 2:
        print(f"OPERATIONAL_READINESS_ERROR checks={','.join(errors)}", file=sys.stderr)
        return 2
    if outcome == 1:
        print(f"OPERATIONAL_READINESS_ALERT checks={','.join(alerts)}", file=sys.stderr)
        return 1
    print(f"OPERATIONAL_READINESS_OK checks={len(results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
