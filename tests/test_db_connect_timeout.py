"""A database that does not answer must make requests fail fast, not hang."""
from __future__ import annotations

from qrfacile_app import db


def test_pg_uses_a_connect_timeout(monkeypatch):
    seen = {}
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@127.0.0.1:5432/x")
    monkeypatch.delenv("QRFACILE_DB_CONNECT_TIMEOUT", raising=False)
    monkeypatch.setattr(db.psycopg, "connect", lambda url, **kw: seen.update(kw) or "conn")
    assert db.pg() == "conn"
    assert seen["connect_timeout"] == 5


def test_connect_timeout_is_configurable_and_bounded(monkeypatch):
    seen = {}
    monkeypatch.setenv("DATABASE_URL", "postgresql://u@127.0.0.1:5432/x")
    monkeypatch.setattr(db.psycopg, "connect", lambda url, **kw: seen.update(kw) or "conn")
    for value, expected in (("12", 12), ("0", 5), ("abc", 5), ("999", 60)):
        monkeypatch.setenv("QRFACILE_DB_CONNECT_TIMEOUT", value)
        db.pg()
        assert seen["connect_timeout"] == expected, value
