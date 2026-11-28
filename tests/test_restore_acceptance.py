from pathlib import Path

from scripts import check_restore_acceptance


SHA = "a" * 40


def _complete_document(backup: Path) -> str:
    checks = "\n".join(
        f"- [x] {label}" for label in check_restore_acceptance.REQUIRED_CHECKS
    )
    return f"""# Restore

## Identità della prova

- Ambiente: [ ] staging  [x] produzione
- SHA candidato (40 caratteri): {SHA}
- Percorso backup verificato: {backup}
- Destinazione isolata del restore: database e filesystem isolati
- Data, ora e fuso: 2026-10-31 Europe/Rome
- Operatore: operatore autorizzato
- Versione PostgreSQL di destinazione: versione compatibile
- Riferimento evidenze interne: verbale interno

## Controlli obbligatori

{checks}

## Esito

Decisione: [x] PASS  [ ] FAIL

- Nome e ruolo del verificatore: verificatore autorizzato
- Data e fuso orario: 2026-10-31 Europe/Rome
- Anomalie residue: nessuna
- Firma o evidenza equivalente: verbale interno
"""


def test_complete_restore_acceptance_matches_release_environment_and_backup(tmp_path):
    backup = tmp_path / "backup"
    assert check_restore_acceptance.validate_restore_acceptance(
        _complete_document(backup),
        expected_release=SHA,
        expected_environment="production",
        expected_backup_path=backup,
    ) == []


def test_restore_acceptance_fails_closed_without_exposing_evidence(tmp_path):
    backup = tmp_path / "backup"
    document = _complete_document(backup)
    document = document.replace("[ ] staging  [x] produzione", "[x] staging  [x] produzione")
    document = document.replace(f"- Percorso backup verificato: {backup}", "- Percorso backup verificato: altro")
    document = document.replace(
        "- [x] `SHA256SUMS` è stato verificato prima del restore.",
        "- [ ] `SHA256SUMS` è stato verificato prima del restore.",
    )
    errors = check_restore_acceptance.validate_restore_acceptance(
        document,
        expected_release=SHA,
        expected_environment="production",
        expected_backup_path=backup,
    )
    assert "ambiente restore diverso da quello atteso o ambiguo" in errors
    assert "backup restore non coincide con il preflight" in errors
    assert any(error.startswith("controllo restore mancante") for error in errors)
    assert "verbale interno" not in " ".join(errors)
