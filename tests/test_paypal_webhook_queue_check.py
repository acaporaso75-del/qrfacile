import psycopg

from scripts import check_paypal_webhook_queue


def test_evaluate_queue_alerts_on_failed_stale_and_size():
    row = {
        "open_count": 11,
        "failed_count": 1,
        "stale_count": 2,
        "oldest_age_minutes": 30,
    }

    assert check_paypal_webhook_queue.evaluate_queue(row, max_open_count=10) == [
        "failed_events",
        "stale_events",
        "queue_size",
    ]


def test_main_reports_only_aggregate_queue_state(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://local.invalid/example")
    monkeypatch.setattr(
        check_paypal_webhook_queue,
        "query_queue",
        lambda *_args, **_kwargs: {
            "open_count": 2,
            "failed_count": 0,
            "stale_count": 0,
            "oldest_age_minutes": 3,
        },
    )

    assert check_paypal_webhook_queue.main([]) == 0
    output = capsys.readouterr()
    assert "PAYPAL_WEBHOOK_QUEUE_OK open=2 failed=0 stale=0 oldest_age_minutes=3" in output.out
    assert "local.invalid" not in output.out + output.err


def test_main_fails_closed_when_database_url_is_missing(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert check_paypal_webhook_queue.main([]) == 2
    assert "DATABASE_URL non configurato" in capsys.readouterr().err


def test_main_does_not_expose_database_errors(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://local.invalid/example")

    def fail(*_args, **_kwargs):
        raise psycopg.OperationalError("sensitive-provider-detail")

    monkeypatch.setattr(check_paypal_webhook_queue, "query_queue", fail)

    assert check_paypal_webhook_queue.main([]) == 2
    output = capsys.readouterr()
    assert "OperationalError" in output.err
    assert "sensitive-provider-detail" not in output.out + output.err
