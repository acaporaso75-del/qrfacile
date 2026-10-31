import argparse
import subprocess

from scripts import check_operational_readiness


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        max_open_age_minutes=15,
        max_open_count=10,
        privacy_warning_days=7,
        incident_assessment_hours=24,
        max_unknown_environment_paid=3,
    )


def test_check_plan_reuses_canonical_probes_without_credentials():
    checks = check_operational_readiness.build_checks(_args())
    assert [check.name for check in checks] == [
        "transactional_email",
        "paypal_webhook_queue",
        "privacy_sla",
        "payment_reconciliation",
    ]
    command_text = " ".join(argument for check in checks for argument in check.arguments)
    assert "DATABASE_URL" not in command_text
    assert "secret" not in command_text.lower()
    assert "check_paypal_webhook_queue.py" in command_text
    assert "check_privacy_sla.py" in command_text
    assert "check_payment_reconciliation.py" in command_text


def test_aggregate_output_never_forwards_child_output(monkeypatch, capsys):
    returncodes = iter((0, 1, 2, 0))

    def fake_run(*_args, **kwargs):
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(
            args=[],
            returncode=next(returncodes),
            stdout="sensitive-child-output",
            stderr="identifier@example.test",
        )

    monkeypatch.setattr(check_operational_readiness.subprocess, "run", fake_run)
    assert check_operational_readiness.main([
        "--max-unknown-environment-paid", "3",
    ]) == 2
    output = capsys.readouterr()
    combined = output.out + output.err
    assert "sensitive-child-output" not in combined
    assert "identifier@example.test" not in combined
    assert "paypal_webhook_queue status=alert" in combined
    assert "privacy_sla status=error" in combined
    assert "OPERATIONAL_READINESS_ERROR checks=privacy_sla" in combined


def test_all_green_returns_single_aggregate_success(monkeypatch, capsys):
    monkeypatch.setattr(
        check_operational_readiness.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, "", ""),
    )
    assert check_operational_readiness.main([]) == 0
    output = capsys.readouterr()
    assert "OPERATIONAL_READINESS_OK checks=4" in output.out
    assert output.err == ""


def test_timeout_is_fail_closed(monkeypatch):
    monkeypatch.setattr(
        check_operational_readiness.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(subprocess.TimeoutExpired("probe", 1)),
    )
    results = check_operational_readiness.execute_checks(
        check_operational_readiness.build_checks(_args()),
        timeout=1,
    )
    assert set(results.values()) == {"error"}
