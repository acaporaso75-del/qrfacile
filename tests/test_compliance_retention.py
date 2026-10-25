from scripts import compliance_retention


class _Cursor:
    def __init__(self, existing):
        self.existing = set(existing)
        self.current_table = ""
        self.rowcount = 0
        self.deletes = []

    def __enter__(self): return self
    def __exit__(self, *_args): return False

    def execute(self, statement, params):
        if statement.startswith("SELECT to_regclass"):
            self.current_table = params[0].split(".", 1)[1]
            return
        self.deletes.append((statement, params))
        self.rowcount = 3

    def fetchone(self):
        return (self.current_table if self.current_table in self.existing else None,)


class _Connection:
    def __init__(self, existing):
        self.cursor_instance = _Cursor(existing)
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def cursor(self): return self.cursor_instance
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def test_retention_dry_run_rolls_back_and_covers_login_failures(monkeypatch):
    connection = _Connection({"login_failures"})
    monkeypatch.setenv("DATABASE_URL", "postgresql://local/test")
    monkeypatch.setattr(compliance_retention.psycopg, "connect", lambda _url: connection)
    result = compliance_retention.execute(dry_run=True)
    assert result["login_failures"] == 3
    assert connection.rollbacks == 1 and connection.commits == 0
    statement, params = connection.cursor_instance.deletes[0]
    assert "extract(epoch FROM now()" in statement
    assert params == (24,)


def test_retention_apply_commits_and_reports_missing_tables(monkeypatch):
    connection = _Connection(set())
    monkeypatch.setenv("DATABASE_URL", "postgresql://local/test")
    monkeypatch.setattr(compliance_retention.psycopg, "connect", lambda _url: connection)
    result = compliance_retention.execute(dry_run=False)
    assert result["login_failures"] == "missing"
    assert connection.commits == 1 and connection.rollbacks == 0
    assert connection.cursor_instance.deletes == []


def test_retention_requires_explicit_database_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    try:
        compliance_retention.execute(dry_run=True)
    except RuntimeError as exc:
        assert "DATABASE_URL" in str(exc)
    else:
        raise AssertionError("missing DATABASE_URL must fail closed")
