from starlette.requests import Request

from qrfacile_app import auth_routes


class _Cursor:
    def __init__(self, request_count):
        self.request_count = request_count
        self.last = ""
        self.queries = []

    def __enter__(self): return self
    def __exit__(self, *_args): return False

    def execute(self, statement, params):
        self.last = " ".join(statement.split())
        self.queries.append((self.last, params))

    def fetchone(self):
        if "FROM users" in self.last:
            return {"id": 7, "email": "customer@example.test"}
        if "COUNT(*) AS request_count" in self.last:
            return {"request_count": self.request_count}
        return None


class _Connection:
    def __init__(self, request_count):
        self.cursor_instance = _Cursor(request_count)
        self.commits = 0
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def cursor(self, **_kwargs): return self.cursor_instance
    def commit(self): self.commits += 1


def _request():
    return Request({
        "type": "http", "method": "POST", "scheme": "https", "path": "/forgot-password",
        "headers": [(b"host", b"example.test")], "client": ("127.0.0.1", 1),
    })


def test_password_reset_limit_is_neutral_and_sends_nothing(monkeypatch):
    connection = _Connection(auth_routes.PASSWORD_RESET_MAX_REQUESTS)
    monkeypatch.setattr(auth_routes, "pg", lambda: connection)
    monkeypatch.setattr(
        auth_routes,
        "_send_password_reset_email",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("email must not be sent")),
    )
    response = auth_routes.forgot_password_post(_request(), "customer@example.test")
    assert response.status_code == 200
    assert auth_routes.PASSWORD_RESET_NEUTRAL_MSG.encode("utf-8") in response.body
    assert connection.commits == 1
    assert "FOR UPDATE" in connection.cursor_instance.queries[0][0]
    assert not any("INSERT INTO password_reset_tokens" in query for query, _ in connection.cursor_instance.queries)


def test_new_reset_invalidates_older_unused_tokens_before_insert():
    source = __import__("pathlib").Path(auth_routes.__file__).read_text(encoding="utf-8")
    revoke = source.index("UPDATE password_reset_tokens SET used_at=%s")
    insert = source.index("INSERT INTO password_reset_tokens")
    assert revoke < insert
    assert "PASSWORD_RESET_WINDOW_SECONDS = 60 * 60" in source
    assert "PASSWORD_RESET_MAX_REQUESTS = 5" in source
