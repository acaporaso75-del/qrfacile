from pathlib import Path

from scripts import check_production_approvals


SHA = "a" * 40


def _approval_section(heading: str, fields: tuple[str, ...]) -> str:
    lines = [f"### {heading}", "", "- Decisione: [x] APPROVATO  [ ] APPROVATO CON CONDIZIONI  [ ] RESPINTO"]
    lines.extend(f"- {field}: evidenza registrata" for field in fields)
    return "\n".join(lines)


def _complete_document() -> str:
    sections = [
        f"Release candidate: `{SHA}`",
        "PR: `#12`, Draft verso `main`",
    ]
    sections.extend(
        _approval_section(heading, fields)
        for heading, fields in check_production_approvals.APPROVAL_SECTIONS.items()
    )
    rows = [
        "| Processo | Responsabile primario | Sostituto | SLA | Canale di escalation | Evidenza prova |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    rows.extend(
        f"| {process} | primario | sostituto | 4 ore | canale interno | prova registrata |"
        for process in check_production_approvals.OPERATIONAL_PROCESSES
    )
    sections.append("\n".join(rows))
    final = ["## 5. Conferma tecnica finale", ""]
    final.extend(f"- [x] {label}" for label in check_production_approvals.FINAL_CHECKS)
    final.extend([
        "",
        "Esito finale: [x] GO  [ ] NO-GO",
        "",
        "- Nome responsabile GO/NO-GO: responsabile autorizzato",
        "- Ruolo: release manager",
        "- Data e fuso orario: 2026-10-29 Europe/Rome",
    ])
    sections.append("\n".join(final))
    return "\n\n".join(sections)


def test_complete_approvals_match_exact_release_and_pr():
    assert check_production_approvals.validate_approvals(
        _complete_document(), expected_release=SHA, expected_pr=12
    ) == []


def test_incomplete_document_reports_field_names_not_field_contents():
    document = _complete_document().replace(
        "- Nome e cognome: evidenza registrata",
        "- Nome e cognome: persona-sensitive",
        1,
    ).replace("- Ruolo: evidenza registrata", "- Ruolo:", 1)
    errors = check_production_approvals.validate_approvals(
        document, expected_release=SHA, expected_pr=12
    )
    assert any("Approvazione commerciale / Ruolo" in error for error in errors)
    assert "persona-sensitive" not in " ".join(errors)


def test_rejected_approval_wrong_sha_and_incomplete_owner_table_fail_closed():
    document = _complete_document()
    document = document.replace(f"Release candidate: `{SHA}`", f"Release candidate: `{'b' * 40}`")
    document = document.replace(
        "[x] APPROVATO  [ ] APPROVATO CON CONDIZIONI  [ ] RESPINTO",
        "[ ] APPROVATO  [ ] APPROVATO CON CONDIZIONI  [x] RESPINTO",
        1,
    )
    document = document.replace(
        "| Monitoraggio disponibilità | primario | sostituto | 4 ore | canale interno | prova registrata |",
        "| Monitoraggio disponibilità |  | sostituto | 4 ore | canale interno | prova registrata |",
    )
    errors = check_production_approvals.validate_approvals(
        document, expected_release=SHA, expected_pr=12
    )
    assert "release candidate non coincide con lo SHA atteso" in errors
    assert "decisione non approvata o ambigua: Approvazione commerciale" in errors
    assert "responsabilità operativa incompleta: Monitoraggio disponibilità" in errors


def test_current_unapproved_template_is_blocked_without_exposing_values():
    path = Path(__file__).resolve().parents[1] / "docs" / "PRODUCTION_APPROVALS_2026-10-29.md"
    errors = check_production_approvals.validate_approvals(
        path.read_text(encoding="utf-8"), expected_release=SHA, expected_pr=12
    )
    assert errors
    assert all("@" not in error for error in errors)
