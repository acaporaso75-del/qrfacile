import pytest

from qrfacile_app.services import ai_review_service


class _Cursor:
    def __init__(self, row):
        self.row = row
        self.result = None
        self.queries = []

    def __enter__(self): return self
    def __exit__(self, *_args): return False

    def execute(self, statement, params):
        query = " ".join(statement.split())
        self.queries.append((query, params))
        if query.startswith("SELECT id, risk_classification"):
            self.result = self.row
        elif query.startswith("UPDATE ai_usage_log"):
            self.result = {"id": int(params[-1]), "human_review_status": params[0]}

    def fetchone(self): return self.result


class _Connection:
    def __init__(self, row):
        self.cursor_instance = _Cursor(row)
        self.commits = 0
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def cursor(self, **_kwargs): return self.cursor_instance
    def commit(self): self.commits += 1


def test_prohibited_ai_output_cannot_be_approved(monkeypatch):
    connection = _Connection({"id": 7, "risk_classification": "prohibited", "human_review_status": "pending"})
    monkeypatch.setattr(ai_review_service, "pg", lambda: connection)
    with pytest.raises(ValueError, match="prohibited_risk_cannot_be_approved"):
        ai_review_service.review_ai_output_record(record_id=7, reviewer_user_id=1, decision="approved")
    assert connection.commits == 0
    assert not any(query.startswith("UPDATE ai_usage_log") for query, _ in connection.cursor_instance.queries)


def test_pending_non_prohibited_output_is_reviewed_under_row_lock(monkeypatch):
    connection = _Connection({"id": 8, "risk_classification": "high", "human_review_status": "pending"})
    monkeypatch.setattr(ai_review_service, "pg", lambda: connection)
    row = ai_review_service.review_ai_output_record(record_id=8, reviewer_user_id=2, decision="approved")
    assert row == {"id": 8, "human_review_status": "approved"}
    assert "FOR UPDATE" in connection.cursor_instance.queries[0][0]
    assert connection.commits == 1


def test_already_reviewed_output_is_not_overwritten(monkeypatch):
    connection = _Connection({"id": 9, "risk_classification": "limited", "human_review_status": "rejected"})
    monkeypatch.setattr(ai_review_service, "pg", lambda: connection)
    assert ai_review_service.review_ai_output_record(record_id=9, reviewer_user_id=2, decision="approved") is None
    assert not any(query.startswith("UPDATE ai_usage_log") for query, _ in connection.cursor_instance.queries)
