#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


FULL_GIT_SHA = re.compile(r"[0-9a-f]{40}")
IDENTITY_FIELDS = (
    "Destinazione isolata del restore",
    "Data, ora e fuso",
    "Operatore",
    "Versione PostgreSQL di destinazione",
    "Riferimento evidenze interne",
)
REQUIRED_CHECKS = (
    "`SHA256SUMS` è stato verificato prima del restore.",
    "Il dump PostgreSQL è stato elencato e ripristinato senza errori in un database isolato.",
    "L’archivio filesystem è stato verificato ed estratto in un percorso isolato.",
    "Le migrazioni candidate sono state applicate due volte senza effetti duplicati.",
    "Precheck e postcheck hanno conservato ordini, accrediti, accettazioni, vini e QR storici.",
    "Il percorso di rollback è disponibile e distinto dal candidato.",
    "Nessuna azione della prova ha scritto su staging o produzione.",
    "Le evidenze non contengono segreti, PII, dump o payload di pagamento.",
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


def validate_restore_acceptance(
    text: str,
    *,
    expected_release: str,
    expected_environment: str,
    expected_backup_path: Path,
) -> list[str]:
    errors: list[str] = []
    expected_label = "produzione" if expected_environment == "production" else "staging"
    if _selected(_field(text, "Ambiente")) != {expected_label}:
        errors.append("ambiente restore diverso da quello atteso o ambiguo")

    release = _field(text, "SHA candidato (40 caratteri)").lower()
    if not FULL_GIT_SHA.fullmatch(release) or release != expected_release:
        errors.append("SHA restore non coincide con il candidato")

    recorded_backup = _field(text, "Percorso backup verificato")
    try:
        matches_backup = Path(recorded_backup).resolve(strict=False) == expected_backup_path.resolve(strict=False)
    except (OSError, ValueError):
        matches_backup = False
    if not recorded_backup or not matches_backup:
        errors.append("backup restore non coincide con il preflight")

    for field in IDENTITY_FIELDS:
        if not _field(text, field):
            errors.append(f"campo restore mancante: {field}")
    for check in REQUIRED_CHECKS:
        if not re.search(rf"^- \[[xX]\]\s*{re.escape(check)}\s*$", text, re.MULTILINE):
            errors.append(f"controllo restore mancante: {check}")

    decision_match = re.search(r"^Decisione:[ \t]*(.*)$", text, re.MULTILINE)
    if _selected(decision_match.group(1) if decision_match else "") != {"PASS"}:
        errors.append("decisione restore non approvata o ambigua")
    for field in FINAL_FIELDS:
        if not _field(text, field):
            errors.append(f"campo esito restore mancante: {field}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida la prova di restore senza stamparne le evidenze")
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--expected-release", required=True)
    parser.add_argument("--expected-environment", choices=("staging", "production"), required=True)
    parser.add_argument("--expected-backup-path", type=Path, required=True)
    args = parser.parse_args(argv)
    release = args.expected_release.strip().lower()
    if not FULL_GIT_SHA.fullmatch(release):
        parser.error("--expected-release deve essere uno SHA Git completo")
    try:
        text = args.path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"RESTORE_ACCEPTANCE_ERROR {type(exc).__name__}")
        return 2
    errors = validate_restore_acceptance(
        text,
        expected_release=release,
        expected_environment=args.expected_environment,
        expected_backup_path=args.expected_backup_path,
    )
    if errors:
        for error in errors:
            print(f"RESTORE_ACCEPTANCE_MISMATCH {error}")
        return 1
    print(f"RESTORE_ACCEPTANCE_OK environment={args.expected_environment} release={release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
