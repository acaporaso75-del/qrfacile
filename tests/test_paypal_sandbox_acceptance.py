from scripts import check_paypal_sandbox_acceptance


SHA = "a" * 40


def _complete(environment: str = "staging", release: str = SHA) -> str:
    checks = "\n".join(
        f"- [x] {label}" for label in check_paypal_sandbox_acceptance.REQUIRED_CHECKS
    )
    return f"""
- Ambiente runtime: [x] {environment}  [ ] produzione
- Ambiente PayPal: [x] Sandbox  [ ] Live
- SHA installato (40 caratteri): {release}
- URL listener HTTPS: https://staging.example.test/paypal/webhook
- Data, ora e fuso: 2026-10-31 10:00 Europe/Rome
- Operatore: Operatore interno
- Riferimento REST app Sandbox: registro interno PP-1
- Riferimento webhook registrato: registro interno PP-2
- Riferimento ordine Sandbox sanitizzato: registro interno PP-3
- Riferimento evidenze interne: ticket PP-4

{checks}

Decisione: [x] PASS  [ ] FAIL
- Nome e ruolo del verificatore: Operatore, SRE
- Data e fuso orario: 2026-10-31 Europe/Rome
- Anomalie residue: nessuna
- Firma o evidenza equivalente: ticket PP-4
"""


def test_complete_paypal_sandbox_acceptance_matches_release_and_environment():
    assert check_paypal_sandbox_acceptance.validate_paypal_sandbox_acceptance(
        _complete(),
        expected_release=SHA,
        expected_environment="staging",
    ) == []


def test_incomplete_or_ambiguous_paypal_sandbox_acceptance_fails_closed():
    text = _complete().replace(
        "- [x] Un evento Sandbox reale, non simulato, ha superato la verifica firma PayPal.",
        "- [ ] Un evento Sandbox reale, non simulato, ha superato la verifica firma PayPal.",
    ).replace("Decisione: [x] PASS  [ ] FAIL", "Decisione: [x] PASS  [x] FAIL")
    errors = check_paypal_sandbox_acceptance.validate_paypal_sandbox_acceptance(
        text,
        expected_release=SHA,
        expected_environment="staging",
    )
    assert any("controllo PayPal Sandbox mancante" in error for error in errors)
    assert "decisione PayPal Sandbox non approvata o ambigua" in errors
    assert "PP-4" not in " ".join(errors)


def test_live_http_or_wrong_identity_is_rejected():
    text = _complete(environment="produzione", release="b" * 40)
    text = text.replace("[x] Sandbox  [ ] Live", "[ ] Sandbox  [x] Live")
    text = text.replace("https://staging.example.test", "http://staging.example.test")
    errors = check_paypal_sandbox_acceptance.validate_paypal_sandbox_acceptance(
        text,
        expected_release=SHA,
        expected_environment="staging",
    )
    assert "ambiente runtime PayPal diverso da quello atteso o ambiguo" in errors
    assert "ambiente PayPal diverso da Sandbox o ambiguo" in errors
    assert "SHA PayPal Sandbox non coincide con il candidato" in errors
    assert "listener PayPal non usa HTTPS" in errors
