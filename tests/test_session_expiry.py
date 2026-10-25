from qrfacile_app import auth_core


class _Cursor:
    def __init__(self, sessions):
        self.sessions = sessions
        self.result = None
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params):
        self.queries.append((statement, params))
        if "app_sessions" in statement:
            raise RuntimeError("compatibility table absent")
        token, cutoff = params
        row = self.sessions.get(token)
        self.result = {"user_id": row["user_id"]} if row and row["created_at"] >= cutoff else None

    def fetchone(self):
        return self.result


class _Connection:
    def __init__(self, sessions):
        self.cursor_instance = _Cursor(sessions)
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self, **_kwargs):
        return self.cursor_instance

    def rollback(self):
        self.rollbacks += 1


def test_server_side_session_expiry_accepts_recent_and_rejects_old_tokens(monkeypatch):
    current = 2_000_000_000
    sessions = {
        "recent": {"user_id": 7, "created_at": current - auth_core.SESSION_MAX_AGE_SECONDS + 1},
        "expired": {"user_id": 8, "created_at": current - auth_core.SESSION_MAX_AGE_SECONDS - 1},
    }
    connections = []

    def connect():
        connection = _Connection(sessions)
        connections.append(connection)
        return connection

    monkeypatch.setattr(auth_core, "now", lambda: current)
    monkeypatch.setattr(auth_core, "pg", connect)
    assert auth_core._session_user_id("recent") == 7
    assert auth_core._session_user_id("expired") is None
    for connection in connections:
        session_queries = [item for item in connection.cursor_instance.queries if "FROM sessions" in item[0]]
        assert len(session_queries) == 1
        assert "created_at>=" in session_queries[0][0]


def test_no_unbounded_session_lookup_remains():
    source = __import__("pathlib").Path(auth_core.__file__).read_text(encoding="utf-8")
    assert "FROM sessions WHERE token=%s LIMIT 1" not in source
    assert "FROM app_sessions WHERE token=%s LIMIT 1" not in source
    assert "SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14" in source
