#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


FULL_GIT_SHA = re.compile(r"[0-9a-f]{40}")
IDENTITY_FIELDS = (
    "URL listener HTTPS",
    "Data, ora e fuso",
    "Operatore",
    "Riferimento REST app Sandbox",
    "Riferimento webhook registrato",
    "Riferimento ordine Sandbox sanitizzato",
    "Riferimento evidenze interne",
)
REQUIRED_CHECKS = (
    "Il listener e registrato sulla stessa REST app Sandbox usata dal checkout di prova.",
    "Un evento Sandbox reale, non simulato, ha superato la verifica firma PayPal.",
    "Header firma mancanti o alterati sono stati rifiutati senza fulfillment.",
    "Ambiente, event ID, ordine, capture, importo e valuta sono stati correlati esattamente.",
    "Solo `PAYMENT.CAPTURE.COMPLETED` ha erogato i crediti previsti, una sola volta.",
    "Il reinvio dello stesso evento dal dashboard PayPal e stato acquisito senza duplicare crediti.",
    "Un tentativo non verificabile o non correlabile resta fail-closed e osservabile.",
    "Eventi diversi da `PAYMENT.CAPTURE.COMPLETED` non hanno erogato crediti e restano auditabili.",
    "Ledger, coda di revisione e alert non espongono payload, event ID, PII o credenziali.",
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


def validate_paypal_sandbox_acceptance(
    text: str,
    *,
    expected_release: str,
    expected_environment: str,
) -> list[str]:
    errors: list[str] = []
    expected_label = "produzione" if expected_environment == "production" else "staging"
    if _selected(_field(text, "Ambiente runtime")) != {expected_label}:
        errors.append("ambiente runtime PayPal diverso da quello atteso o ambiguo")
    if _selected(_field(text, "Ambiente PayPal")) != {"Sandbox"}:
        errors.append("ambiente PayPal diverso da Sandbox o ambiguo")

    release = _field(text, "SHA installato (40 caratteri)").lower()
    if not FULL_GIT_SHA.fullmatch(release) or release != expected_release:
        errors.append("SHA PayPal Sandbox non coincide con il candidato")

    for field in IDENTITY_FIELDS:
        if not _field(text, field):
            errors.append(f"campo PayPal Sandbox mancante: {field}")
    listener = _field(text, "URL listener HTTPS").lower()
    if not listener.startswith("https://"):
        errors.append("listener PayPal non usa HTTPS")
    for check in REQUIRED_CHECKS:
        if not re.search(rf"^- \[[xX]\]\s*{re.escape(check)}\s*$", text, re.MULTILINE):
            errors.append(f"controllo PayPal Sandbox mancante: {check}")

    decision_match = re.search(r"^Decisione:[ \t]*(.*)$", text, re.MULTILINE)
    if _selected(decision_match.group(1) if decision_match else "") != {"PASS"}:
        errors.append("decisione PayPal Sandbox non approvata o ambigua")
    for field in FINAL_FIELDS:
        if not _field(text, field):
            errors.append(f"campo esito PayPal Sandbox mancante: {field}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Valida la prova webhook PayPal Sandbox senza stamparne le evidenze"
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
        print(f"PAYPAL_SANDBOX_ACCEPTANCE_ERROR {type(exc).__name__}")
        return 2
    errors = validate_paypal_sandbox_acceptance(
        text,
        expected_release=release,
        expected_environment=args.expected_environment,
    )
    if errors:
        for error in errors:
            print(f"PAYPAL_SANDBOX_ACCEPTANCE_MISMATCH {error}")
        return 1
    print(f"PAYPAL_SANDBOX_ACCEPTANCE_OK environment={args.expected_environment} release={release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
