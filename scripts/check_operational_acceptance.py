#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


FULL_GIT_SHA = re.compile(r"[0-9a-f]{40}")
IDENTITY_FIELDS = (
    "URL origine",
    "Data, ora e fuso",
    "Operatore",
    "Riferimento destinatario interno autorizzato",
    "Riferimento scheduler/monitor",
    "Riferimento evidenze interne",
)
REQUIRED_CHECKS = (
    "`check_transactional_email.py` ha restituito `TRANSACTIONAL_EMAIL_CONFIG_OK`.",
    "Un messaggio transazionale di prova e stato consegnato alla casella interna autorizzata.",
    "Un alert sintetico non verde e stato consegnato al responsabile operativo nominato.",
    "L'alert contiene soltanto nomi e stati aggregati, senza payload, event ID o PII.",
    "Il monitor schedulato esegue i probe PayPal webhook e privacy SLA con il runtime previsto.",
    "Un errore di consegna SMTP produce un esito fail-closed osservabile.",
    "Le anomalie residue hanno responsabile e SLA documentati.",
    "Le evidenze non contengono indirizzi personali, credenziali, token o segreti.",
)
FINAL_FIELDS = (
    "Nome e ruolo del verificatore",
    "Data e fuso orario",
    "Anomalie residue",
    "Firma o evidenza equivalente",
)


def _field(text: str, label: str) -> str:
    match = re.search(rf"^- {re.escape(label)}:[ \t]*(.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _selected(value: str) -> set[str]:
    return {
        label.strip()
        for checked, label in re.findall(r"\[([ xX])\]\s*([^[]+?)(?=\s*\[|$)", value)
        if checked.lower() == "x"
    }


def validate_operational_acceptance(
    text: str,
    *,
    expected_release: str,
    expected_environment: str,
) -> list[str]:
    errors: list[str] = []
    expected_label = "produzione" if expected_environment == "production" else "staging"
    if _selected(_field(text, "Ambiente")) != {expected_label}:
        errors.append("ambiente operativo diverso da quello atteso o ambiguo")

    release = _field(text, "SHA installato (40 caratteri)").lower()
    if not FULL_GIT_SHA.fullmatch(release) or release != expected_release:
        errors.append("SHA operativo non coincide con il candidato")

    for field in IDENTITY_FIELDS:
        if not _field(text, field):
            errors.append(f"campo operativo mancante: {field}")
    for check in REQUIRED_CHECKS:
        if not re.search(rf"^- \[[xX]\]\s*{re.escape(check)}\s*$", text, re.MULTILINE):
            errors.append(f"controllo operativo mancante: {check}")

    decision_match = re.search(r"^Decisione:[ \t]*(.*)$", text, re.MULTILINE)
    if _selected(decision_match.group(1) if decision_match else "") != {"PASS"}:
        errors.append("decisione operativa non approvata o ambigua")
    for field in FINAL_FIELDS:
        if not _field(text, field):
            errors.append(f"campo esito operativo mancante: {field}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Valida la prova SMTP/alert senza stamparne le evidenze"
    )
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--expected-release", required=True)
    parser.add_argument("--expected-environment", choices=("staging", "production"), required=True)
    args = parser.parse_args(argv)
    release = args.expected_release.strip().lower()
    if not FULL_GIT_SHA.fullmatch(release):
        parser.error("--expected-release deve essere uno SHA Git completo")
    try:
        text = args.path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"OPERATIONAL_ACCEPTANCE_ERROR {type(exc).__name__}")
        return 2
    errors = validate_operational_acceptance(
        text,
        expected_release=release,
        expected_environment=args.expected_environment,
    )
    if errors:
        for error in errors:
            print(f"OPERATIONAL_ACCEPTANCE_MISMATCH {error}")
        return 1
    print(f"OPERATIONAL_ACCEPTANCE_OK environment={args.expected_environment} release={release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
