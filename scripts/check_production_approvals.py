#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


FULL_GIT_SHA = re.compile(r"[0-9a-f]{40}")
APPROVAL_SECTIONS = {
    "Approvazione commerciale": (
        "Nome e cognome",
        "Ruolo",
        "Organizzazione",
        "Data e fuso orario",
        "Perimetro approvato",
        "Claim commerciali autorizzati",
        "Condizioni o modifiche richieste",
        "Riferimento documento/e-mail/verbale",
        "Firma o evidenza equivalente",
    ),
    "Approvazione contabile": (
        "Nome e cognome",
        "Qualifica/Albo",
        "Studio",
        "Data e fuso orario",
        "Paesi e regimi fiscali autorizzati al self-service",
        "Processo di fatturazione approvato",
        "Processo di riconciliazione/rimborso approvato",
        "Condizioni o modifiche richieste",
        "Riferimento parere/verbale",
        "Firma o evidenza equivalente",
    ),
    "Approvazione legale/DPO": (
        "Nome e cognome",
        "Ruolo e organizzazione",
        "Data e fuso orario",
        "Documenti/versioni approvati",
        "Trattamenti e casi d’uso AI approvati",
        "SLA diritti interessati",
        "SLA incidenti",
        "Condizioni o modifiche richieste",
        "Riferimento parere/verbale",
        "Firma o evidenza equivalente",
    ),
    "Approvazione operativa": (
        "Responsabile del rilascio",
        "Responsabile del rollback",
        "Finestra di rilascio autorizzata",
        "Durata osservazione post-deploy",
        "Canale incidenti",
        "Data e fuso orario",
        "Firma o evidenza equivalente",
    ),
}
OPERATIONAL_PROCESSES = (
    "Monitoraggio disponibilità",
    "Alert applicativi/database",
    "Backup e restore",
    "Richieste privacy",
    "Incidenti sicurezza",
    "Revisione umana AI",
    "Supporto clienti",
    "Fatturazione",
    "Riconciliazione PayPal",
    "Rimborsi/chargeback",
)
FINAL_CHECKS = (
    "Tutte le sezioni precedenti sono compilate e approvate.",
    "Eventuali condizioni sono state trasformate in issue verificabili e chiuse.",
    "Il percorso del secret store PayPal Live è stato comunicato senza esporre segreti.",
    "Backup, baseline, PR, SHA e CI coincidono ancora con il release gate.",
    "La PR #12 può essere convertita da Draft a Ready.",
)
FINAL_FIELDS = (
    "Nome responsabile GO/NO-GO",
    "Ruolo",
    "Data e fuso orario",
)
EVIDENCE_ONLY_PATHS = {
    "docs/ACCESSIBILITY_ACCEPTANCE_2026-10-29.md",
    "docs/OPERATIONAL_ACCEPTANCE_2026-10-31.md",
    "docs/PAYMENT_REFUND_DISPUTE_RUNBOOK_2026-10-29.md",
    "docs/PAYPAL_LIVE_READINESS_2026-10-29.md",
    "docs/PRODUCTION_APPROVALS_2026-10-29.md",
    "docs/PRODUCTION_DEPLOY_RUNBOOK_2026-10-29.md",
    "docs/PRODUCTION_RELEASE_GATE_2026-10-29.md",
    "docs/RESTORE_ACCEPTANCE_2026-10-31.md",
    "scripts/check_production_approvals.py",
    "scripts/check_accessibility_acceptance.py",
    "scripts/check_operational_acceptance.py",
    "scripts/check_release_preflight.py",
    "scripts/check_restore_acceptance.py",
    "tests/test_accessibility_acceptance.py",
    "tests/test_operational_acceptance.py",
    "tests/test_production_approvals.py",
    "tests/test_release_preflight.py",
    "tests/test_restore_acceptance.py",
}


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"^### {re.escape(heading)}\s*$([\s\S]*?)(?=^## |^### |\Z)",
        text,
        flags=re.MULTILINE,
    )
    return match.group(1) if match else ""


def _field_value(section: str, label: str) -> str:
    match = re.search(rf"^- {re.escape(label)}:[ \t]*(.*)$", section, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _is_meaningful(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized or normalized in {"-", "tbd", "todo", "da definire", "da compilare"}:
        return False
    return not ("<" in value or ">" in value)


def _selected_options(line: str) -> set[str]:
    return {
        label.strip()
        for checked, label in re.findall(r"\[([ xX])\]\s*([^[]+?)(?=\s{2,}\[|$)", line)
        if checked.lower() == "x"
    }


def _checked_line(section: str, label: str) -> bool:
    return bool(
        re.search(
            rf"^- \[[xX]\]\s*{re.escape(label)}\s*$",
            section,
            flags=re.MULTILINE,
        )
    )


def approved_release(text: str) -> str | None:
    match = re.search(r"^Release candidate:\s*`([0-9a-f]{40})`\s*$", text, re.MULTILINE)
    return match.group(1) if match else None


def evidence_only_changes(repo_root: Path, approved: str, current: str) -> set[str]:
    subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", approved, current],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--name-only", f"{approved}..{current}", "--"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return {line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()}


def validate_approvals(
    text: str,
    *,
    expected_release: str,
    expected_pr: int,
    post_approval_paths: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    approved = approved_release(text)
    if not approved:
        errors.append("release candidate non coincide con lo SHA atteso")
    elif approved != expected_release:
        if post_approval_paths is None:
            errors.append("release candidate non coincide con lo SHA atteso")
        elif not post_approval_paths.issubset(EVIDENCE_ONLY_PATHS):
            errors.append("il candidato contiene modifiche successive non limitate alle evidenze")
    pr_match = re.search(r"^PR:\s*`#(\d+)`", text, re.MULTILINE)
    if not pr_match or int(pr_match.group(1)) != expected_pr:
        errors.append("PR approvata non coincide con quella attesa")

    for heading, required_fields in APPROVAL_SECTIONS.items():
        section = _section(text, heading)
        if not section:
            errors.append(f"sezione assente: {heading}")
            continue
        decision_line = next(
            (line for line in section.splitlines() if line.startswith("- Decisione:")),
            "",
        )
        selected = _selected_options(decision_line)
        allowed = {"APPROVATO", "APPROVATO CON CONDIZIONI"}
        if len(selected) != 1 or not selected.issubset(allowed):
            errors.append(f"decisione non approvata o ambigua: {heading}")
        for field in required_fields:
            if not _is_meaningful(_field_value(section, field)):
                errors.append(f"campo obbligatorio mancante: {heading} / {field}")

    table_rows: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] in OPERATIONAL_PROCESSES:
            table_rows[cells[0]] = cells[1:]
    for process in OPERATIONAL_PROCESSES:
        values = table_rows.get(process, [])
        if len(values) != 5 or any(not _is_meaningful(value) for value in values):
            errors.append(f"responsabilità operativa incompleta: {process}")

    final_section = re.search(r"^## 5\. Conferma tecnica finale\s*$([\s\S]*)", text, re.MULTILINE)
    final_text = final_section.group(1) if final_section else ""
    for label in FINAL_CHECKS:
        if not _checked_line(final_text, label):
            errors.append(f"conferma finale non selezionata: {label}")
    outcome_line = next(
        (line for line in final_text.splitlines() if line.startswith("Esito finale:")),
        "",
    )
    if _selected_options(outcome_line) != {"GO"}:
        errors.append("esito finale diverso da GO o ambiguo")
    for field in FINAL_FIELDS:
        if not _is_meaningful(_field_value(final_text, field)):
            errors.append(f"campo GO/NO-GO mancante: {field}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Valida le approvazioni esterne QRFacile senza stamparne i contenuti"
    )
    parser.add_argument("--approvals-path", type=Path, required=True)
    parser.add_argument("--expected-release", required=True)
    parser.add_argument("--expected-pr", type=int, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args(argv)
    release = args.expected_release.strip().lower()
    if not FULL_GIT_SHA.fullmatch(release):
        parser.error("--expected-release deve essere uno SHA Git completo")
    if args.expected_pr <= 0:
        parser.error("--expected-pr deve essere positivo")
    try:
        text = args.approvals_path.read_text(encoding="utf-8")
        approved = approved_release(text)
        changed_paths = (
            evidence_only_changes(args.repo_root.resolve(), approved, release)
            if approved and approved != release
            else set()
        )
    except (OSError, subprocess.SubprocessError):
        print("PRODUCTION_APPROVALS_ERROR document_unavailable", file=sys.stderr)
        return 2
    errors = validate_approvals(
        text,
        expected_release=release,
        expected_pr=args.expected_pr,
        post_approval_paths=changed_paths,
    )
    if errors:
        for error in errors:
            print(f"PRODUCTION_APPROVALS_INCOMPLETE {error}", file=sys.stderr)
        return 1
    print(f"PRODUCTION_APPROVALS_OK release={release} pr={args.expected_pr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
