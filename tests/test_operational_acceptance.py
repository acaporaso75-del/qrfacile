from scripts import check_operational_acceptance


SHA = "a" * 40


def _complete(environment: str = "staging", release: str = SHA) -> str:
    checks = "\n".join(
        f"- [x] {label}" for label in check_operational_acceptance.REQUIRED_CHECKS
    )
    return f"""
- Ambiente: [x] {environment}  [ ] produzione
- SHA installato (40 caratteri): {release}
- URL origine: https://staging.example.test
- Data, ora e fuso: 2026-10-31 09:00 Europe/Rome
- Operatore: Operatore interno
- Riferimento destinatario interno autorizzato: ticket OPS-1
- Riferimento scheduler/monitor: job monitor-1
- Riferimento evidenze interne: ticket OPS-1

{checks}

Decisione: [x] PASS  [ ] FAIL
- Nome e ruolo del verificatore: Operatore, SRE
- Data e fuso orario: 2026-10-31 Europe/Rome
- Anomalie residue: nessuna
- Firma o evidenza equivalente: ticket OPS-1
"""


def test_complete_operational_acceptance_matches_release_and_environment():
    assert check_operational_acceptance.validate_operational_acceptance(
        _complete(),
        expected_release=SHA,
        expected_environment="staging",
    ) == []


def test_incomplete_or_ambiguous_operational_acceptance_fails_closed():
    text = _complete().replace(
        "- [x] Un alert sintetico non verde e stato consegnato al responsabile operativo nominato.",
        "- [ ] Un alert sintetico non verde e stato consegnato al responsabile operativo nominato.",
    ).replace("Decisione: [x] PASS  [ ] FAIL", "Decisione: [x] PASS  [x] FAIL")
    errors = check_operational_acceptance.validate_operational_acceptance(
        text,
        expected_release=SHA,
        expected_environment="staging",
    )
    assert any("controllo operativo mancante" in error for error in errors)
    assert "decisione operativa non approvata o ambigua" in errors
    assert "OPS-1" not in " ".join(errors)


def test_wrong_release_or_environment_is_rejected():
    errors = check_operational_acceptance.validate_operational_acceptance(
        _complete(environment="produzione", release="b" * 40),
        expected_release=SHA,
        expected_environment="staging",
    )
    assert "ambiente operativo diverso da quello atteso o ambiguo" in errors
    assert "SHA operativo non coincide con il candidato" in errors
