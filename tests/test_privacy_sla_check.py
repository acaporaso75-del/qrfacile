import psycopg

from scripts import check_privacy_sla


def test_evaluate_sla_state_alerts_without_record_identifiers():
    row = {
        "privacy_overdue": 1,
        "privacy_due_soon": 2,
        "high_critical_open": 1,
        "unowned_incidents": 1,
        "authority_notification_pending": 1,
        "data_subject_notification_pending": 1,
        "personal_data_assessment_overdue": 1,
    }
    assert check_privacy_sla.evaluate_sla_state(row) == [
        "privacy_overdue",
        "privacy_due_soon",
        "high_critical_incident",
        "unowned_incident",
        "authority_notification_pending",
        "data_subject_notification_pending",
        "personal_data_assessment_overdue",
    ]


def test_main_reports_aggregate_ok_state(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://local.invalid/example")
    monkeypatch.setattr(
        check_privacy_sla,
        "query_sla_state",
        lambda *_args, **_kwargs: {
            "privacy_open": 0,
            "incidents_open": 0,
        },
    )

    assert check_privacy_sla.main([]) == 0
    output = capsys.readouterr()
    assert output.out.startswith("PRIVACY_SLA_OK privacy_open=0")
    assert "local.invalid" not in output.out + output.err


def test_main_fails_closed_without_database_url(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert check_privacy_sla.main([]) == 2
    assert "DATABASE_URL non configurato" in capsys.readouterr().err


def test_main_redacts_database_error(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://local.invalid/example")

    def fail(*_args, **_kwargs):
        raise psycopg.OperationalError("sensitive-database-detail")

    monkeypatch.setattr(check_privacy_sla, "query_sla_state", fail)
    assert check_privacy_sla.main([]) == 2
    output = capsys.readouterr()
    assert "OperationalError" in output.err
    assert "sensitive-database-detail" not in output.out + output.err
