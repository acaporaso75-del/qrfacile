from scripts import check_accessibility_acceptance


SHA = "a" * 40


def _complete_document() -> str:
    rows = [
        "| ID | Percorso | Azioni da verificare | Esito | Evidenza / difetto |",
        "| --- | --- | --- | --- | --- |",
    ]
    rows.extend(
        f"| A{number:02d} | /path | verifica | [x] PASS [ ] FAIL | evidenza interna |"
        for number in range(1, 13)
    )
    checks = "\n".join(
        f"- [x] {label}" for label in check_accessibility_acceptance.FINAL_CHECKS
    )
    return f"""# Accettazione

## Identità della prova

- Ambiente: [ ] staging  [x] produzione
- URL origine: https://www.qrfacile.it
- SHA installato (40 caratteri): {SHA}
- Run ID Compliance CI: 12345
- Data, ora e fuso: 2026-10-30 Europe/Rome
- Operatore: operatore autorizzato
- Browser e versione: browser test
- Sistema operativo: sistema test
- Screen reader e versione: lettore test
- Zoom verificato: [x] 200%  [x] 400%
- Account di prova cantina: account sintetico
- Account di prova Studio: account sintetico
- Etichetta assegnata allo Studio: etichetta sintetica

## Matrice dei percorsi essenziali

{chr(10).join(rows)}

## Registro difetti

| ID | Gravità | Percorso | Passi di riproduzione | Risultato atteso | Risultato osservato | Issue / commit correttivo | Retest |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |

## Esito

{checks}

Decisione: [x] PASS  [ ] PASS CON LIMITI  [ ] FAIL

- Nome e ruolo del verificatore: verificatore autorizzato
- Data e fuso orario: 2026-10-30 Europe/Rome
- Limiti residui: nessuno
- Riferimenti alle evidenze: registro interno
- Firma o evidenza equivalente: verbale interno
"""


def test_complete_accessibility_acceptance_matches_release_and_environment():
    assert check_accessibility_acceptance.validate_accessibility_acceptance(
        _complete_document(),
        expected_release=SHA,
        expected_environment="production",
    ) == []


def test_incomplete_or_ambiguous_acceptance_fails_closed_without_evidence_values():
    document = _complete_document()
    document = document.replace("[ ] staging  [x] produzione", "[x] staging  [x] produzione")
    document = document.replace("[x] PASS [ ] FAIL", "[ ] PASS [x] FAIL", 1)
    document = document.replace("- Browser e versione: browser test", "- Browser e versione:")
    errors = check_accessibility_acceptance.validate_accessibility_acceptance(
        document,
        expected_release=SHA,
        expected_environment="production",
    )
    assert "ambiente accessibilità diverso da quello atteso o ambiguo" in errors
    assert "percorso accessibilità non superato: A01" in errors
    assert "campo accessibilità mancante: Browser e versione" in errors
    assert "evidenza interna" not in " ".join(errors)


def test_open_high_defect_blocks_acceptance():
    document = _complete_document().replace(
        "|  |  |  |  |  |  |  |  |",
        "| AX1 | HIGH | /login | passi | atteso | osservato | issue-1 | APERTO |",
    )
    errors = check_accessibility_acceptance.validate_accessibility_acceptance(
        document,
        expected_release=SHA,
        expected_environment="production",
    )
    assert errors == ["difetto accessibilità grave ancora aperto"]
