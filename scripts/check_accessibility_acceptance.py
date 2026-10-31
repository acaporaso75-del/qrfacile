#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


FULL_GIT_SHA = re.compile(r"[0-9a-f]{40}")
REQUIRED_FIELDS = (
    "URL origine",
    "Run ID Compliance CI",
    "Data, ora e fuso",
    "Operatore",
    "Browser e versione",
    "Sistema operativo",
    "Screen reader e versione",
    "Account di prova cantina",
    "Account di prova Studio",
    "Etichetta assegnata allo Studio",
)
REQUIRED_PATHS = tuple(f"A{number:02d}" for number in range(1, 13))
FINAL_CHECKS = (
    "Tutti i percorsi essenziali sono stati provati sullo SHA indicato.",
    "Nessun `BLOCKER` o `HIGH` è aperto.",
    "Le eccezioni residue hanno responsabile, scadenza e approvazione.",
    "Le evidenze non contengono PII, password, token o segreti.",
)
FINAL_FIELDS = (
    "Nome e ruolo del verificatore",
    "Data e fuso orario",
    "Limiti residui",
    "Riferimenti alle evidenze",
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


def _table_rows(section: str) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells:
            rows[cells[0]] = cells[1:]
    return rows


def validate_accessibility_acceptance(
    text: str,
    *,
    expected_release: str,
    expected_environment: str,
) -> list[str]:
    errors: list[str] = []
    environment = _selected(_field(text, "Ambiente"))
    expected_label = "produzione" if expected_environment == "production" else "staging"
    if environment != {expected_label}:
        errors.append("ambiente accessibilità diverso da quello atteso o ambiguo")

    release = _field(text, "SHA installato (40 caratteri)").lower()
    if not FULL_GIT_SHA.fullmatch(release) or release != expected_release:
        errors.append("SHA accessibilità non coincide con il candidato")
    for field in REQUIRED_FIELDS:
        if not _field(text, field):
            errors.append(f"campo accessibilità mancante: {field}")
    if _selected(_field(text, "Zoom verificato")) != {"200%", "400%"}:
        errors.append("zoom accessibilità 200% e 400% non entrambi verificati")

    matrix_match = re.search(
        r"^## Matrice dei percorsi essenziali\s*$([\s\S]*?)(?=^## )",
        text,
        re.MULTILINE,
    )
    matrix_rows = _table_rows(matrix_match.group(1) if matrix_match else "")
    for path_id in REQUIRED_PATHS:
        cells = matrix_rows.get(path_id, [])
        outcome = _selected(cells[2]) if len(cells) >= 3 else set()
        if outcome != {"PASS"}:
            errors.append(f"percorso accessibilità non superato: {path_id}")

    defects_match = re.search(
        r"^## Registro difetti\s*$([\s\S]*?)(?=^## Esito)",
        text,
        re.MULTILINE,
    )
    defect_rows = _table_rows(defects_match.group(1) if defects_match else "")
    for defect_id, cells in defect_rows.items():
        if not defect_id or defect_id in {"ID", "---"} or len(cells) < 7:
            continue
        severity = cells[0].upper()
        retest = cells[6].strip().upper()
        if severity not in {"BLOCKER", "HIGH", "MEDIUM", "LOW"}:
            errors.append("gravità difetto accessibilità non valida")
        if severity in {"BLOCKER", "HIGH"} and retest not in {"PASS", "CHIUSO", "CLOSED", "OK"}:
            errors.append("difetto accessibilità grave ancora aperto")

    final_match = re.search(r"^## Esito\s*$([\s\S]*)", text, re.MULTILINE)
    final_text = final_match.group(1) if final_match else ""
    for label in FINAL_CHECKS:
        if not re.search(rf"^- \[[xX]\]\s*{re.escape(label)}\s*$", final_text, re.MULTILINE):
            errors.append(f"conferma accessibilità mancante: {label}")
    decision_match = re.search(r"^Decisione:[ \t]*(.*)$", final_text, re.MULTILINE)
    decision = _selected(decision_match.group(1) if decision_match else "")
    if len(decision) != 1 or not decision.issubset({"PASS", "PASS CON LIMITI"}):
        errors.append("decisione accessibilità non approvata o ambigua")
    for field in FINAL_FIELDS:
        if not _field(final_text, field):
            errors.append(f"campo esito accessibilità mancante: {field}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida il protocollo accessibilità senza stamparne le evidenze")
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
        print(f"ACCESSIBILITY_ACCEPTANCE_ERROR {type(exc).__name__}")
        return 2
    errors = validate_accessibility_acceptance(
        text,
        expected_release=release,
        expected_environment=args.expected_environment,
    )
    if errors:
        for error in errors:
            print(f"ACCESSIBILITY_ACCEPTANCE_MISMATCH {error}")
        return 1
    print(f"ACCESSIBILITY_ACCEPTANCE_OK environment={args.expected_environment} release={release}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
