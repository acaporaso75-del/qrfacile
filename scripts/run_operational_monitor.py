#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from email.utils import parseaddr
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qrfacile_app.services.transactional_email import send_text_email
from scripts.check_operational_readiness import (
    add_check_arguments,
    build_checks,
    execute_checks,
    result_code,
    validate_check_arguments,
)


ALERT_RECIPIENT_ENV = "QRFACILE_OPERATIONAL_ALERT_TO"


def load_alert_recipient(environ: Mapping[str, str] | None = None) -> str | None:
    source = os.environ if environ is None else environ
    candidate = (source.get(ALERT_RECIPIENT_ENV) or "").strip()
    if not candidate or len(candidate) > 254 or "\n" in candidate or "\r" in candidate:
        return None
    display_name, address = parseaddr(candidate)
    if display_name or address != candidate or address.count("@") != 1:
        return None
    local_part, domain = address.rsplit("@", 1)
    if not local_part or not domain or "." not in domain:
        return None
    return address


def sanitized_alert_body(results: dict[str, str]) -> str:
    lines = [
        "QRFacile ha rilevato un esito operativo che richiede verifica.",
        "Il messaggio non contiene payload, identificativi evento o dati personali.",
        "",
    ]
    lines.extend(f"- {name}: {status}" for name, status in sorted(results.items()))
    return "\n".join(lines)


def deliver_alert(results: dict[str, str], *, environ: Mapping[str, str] | None = None) -> bool:
    recipient = load_alert_recipient(environ)
    if recipient is None:
        return False
    sent, _error = send_text_email(
        to_email=recipient,
        subject="QRFacile: verifica operativa richiesta",
        body=sanitized_alert_body(results),
    )
    return sent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Esegue i probe QRFacile e notifica solo esiti non verdi senza dati sensibili"
    )
    add_check_arguments(parser)
    args = parser.parse_args(argv)
    validate_check_arguments(parser, args)

    results = execute_checks(build_checks(args), timeout=args.timeout_per_check)
    outcome = result_code(results)
    for name, status in results.items():
        print(f"OPERATIONAL_MONITOR_CHECK name={name} status={status}")
    if outcome == 0:
        print(f"OPERATIONAL_MONITOR_OK checks={len(results)}")
        return 0
    if not deliver_alert(results):
        print("OPERATIONAL_MONITOR_DELIVERY_ERROR", file=sys.stderr)
        return 2
    print(f"OPERATIONAL_MONITOR_ALERT_SENT checks={len(results)}", file=sys.stderr)
    return outcome


if __name__ == "__main__":
    raise SystemExit(main())
