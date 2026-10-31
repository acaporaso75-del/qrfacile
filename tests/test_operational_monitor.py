import argparse

from scripts import check_operational_readiness, run_operational_monitor


def _results(status: str = "ok") -> dict[str, str]:
    return {
        "transactional_email": status,
        "paypal_webhook_queue": status,
        "privacy_sla": status,
        "payment_reconciliation": status,
    }


def test_alert_recipient_is_fail_closed_and_rejects_header_injection():
    assert run_operational_monitor.load_alert_recipient({}) is None
    assert run_operational_monitor.load_alert_recipient({
        run_operational_monitor.ALERT_RECIPIENT_ENV: "Ops <ops@example.test>",
    }) is None
    assert run_operational_monitor.load_alert_recipient({
        run_operational_monitor.ALERT_RECIPIENT_ENV: "ops@example.test\nBcc: external@example.test",
    }) is None
    assert run_operational_monitor.load_alert_recipient({
        run_operational_monitor.ALERT_RECIPIENT_ENV: "ops@example.test",
    }) == "ops@example.test"


def test_green_monitor_does_not_send_email(monkeypatch, capsys):
    monkeypatch.setattr(run_operational_monitor, "execute_checks", lambda *_args, **_kwargs: _results())
    monkeypatch.setattr(
        run_operational_monitor,
        "send_text_email",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected delivery")),
    )
    assert run_operational_monitor.main([]) == 0
    output = capsys.readouterr()
    assert "OPERATIONAL_MONITOR_OK checks=4" in output.out
    assert output.err == ""


def test_alert_email_contains_only_aggregate_statuses(monkeypatch):
    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return True, ""

    monkeypatch.setattr(run_operational_monitor, "send_text_email", fake_send)
    results = _results()
    results["paypal_webhook_queue"] = "alert"
    assert run_operational_monitor.deliver_alert(
        results,
        environ={run_operational_monitor.ALERT_RECIPIENT_ENV: "ops@example.test"},
    ) is True
    assert captured["to_email"] == "ops@example.test"
    assert "paypal_webhook_queue: alert" in captured["body"]
    assert "payload" in captured["body"]
    assert "event_id" not in captured["body"]
    assert "DATABASE_URL" not in captured["body"]


def test_non_green_monitor_fails_closed_when_delivery_is_unavailable(monkeypatch, capsys):
    results = _results()
    results["privacy_sla"] = "alert"
    monkeypatch.setattr(run_operational_monitor, "execute_checks", lambda *_args, **_kwargs: results)
    monkeypatch.setattr(run_operational_monitor, "deliver_alert", lambda *_args, **_kwargs: False)
    assert run_operational_monitor.main([]) == 2
    output = capsys.readouterr()
    assert "OPERATIONAL_MONITOR_DELIVERY_ERROR" in output.err
    assert "privacy_sla status=alert" in output.out


def test_shared_argument_validation_and_result_priority():
    parser = argparse.ArgumentParser()
    check_operational_readiness.add_check_arguments(parser)
    args = parser.parse_args([])
    check_operational_readiness.validate_check_arguments(parser, args)
    assert check_operational_readiness.result_code(_results()) == 0
    results = _results()
    results["privacy_sla"] = "alert"
    assert check_operational_readiness.result_code(results) == 1
    results["transactional_email"] = "error"
    assert check_operational_readiness.result_code(results) == 2
