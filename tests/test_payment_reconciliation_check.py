import psycopg

from scripts import check_payment_reconciliation


def test_product_credit_checks_preserve_historical_pack_entitlements():
    orders = [{"id": 7, "pack": "start", "amount_cents": 7900, "commercial_snapshot": None}]
    grants = [{"ref_id": 7, "credit_type": "wine", "units": 20, "entries": 1}]
    assert check_payment_reconciliation._product_credit_checks(orders, grants) == {
        "product_conditions_invalid": 0,
        "credit_grant_mismatch": 0,
        "duplicate_grant_groups": 0,
    }


def test_evaluate_reconciliation_alerts_every_invariant():
    row = {
        "paid_missing_capture": 1,
        "paid_missing_timestamp": 1,
        "paid_invalid_amount_currency": 1,
        "unknown_environment_paid": 2,
        "duplicate_capture_groups": 1,
        "orphan_order_grants": 1,
        "nonpaid_order_grants": 1,
        "grant_user_mismatch": 1,
        "refund_review_open": 1,
        "product_conditions_invalid": 1,
        "credit_grant_mismatch": 1,
        "duplicate_grant_groups": 1,
    }
    reasons = check_payment_reconciliation.evaluate_reconciliation(
        row,
        max_unknown_environment_paid=0,
    )
    assert "unknown_environment_paid" in reasons
    assert len(reasons) == 12


def test_main_reports_aggregate_ok_state(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://local.invalid/example")
    monkeypatch.setattr(
        check_payment_reconciliation,
        "query_reconciliation",
        lambda *_args, **_kwargs: {"paid_orders": 3},
    )
    assert check_payment_reconciliation.main([]) == 0
    output = capsys.readouterr()
    assert output.out.startswith("PAYMENT_RECONCILIATION_OK paid_orders=3")
    assert "local.invalid" not in output.out + output.err


def test_main_fails_closed_and_redacts_database_errors(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://local.invalid/example")

    def fail(*_args, **_kwargs):
        raise psycopg.OperationalError("sensitive-database-detail")

    monkeypatch.setattr(check_payment_reconciliation, "query_reconciliation", fail)
    assert check_payment_reconciliation.main([]) == 2
    output = capsys.readouterr()
    assert "OperationalError" in output.err
    assert "sensitive-database-detail" not in output.out + output.err


def test_main_fails_closed_without_database_url(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert check_payment_reconciliation.main([]) == 2
    assert "DATABASE_URL non configurato" in capsys.readouterr().err
