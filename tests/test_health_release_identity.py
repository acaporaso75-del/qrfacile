from __future__ import annotations

import json
from pathlib import Path

import pytest

from qrfacile_app import health as health_module
from qrfacile_app.runtime_config import RuntimeConfig


SHA = "b0c0b44d6865531cf51635db48f9dbcf0ec5ca14"  # pragma: allowlist secret


def _config(environment: str, root: Path) -> RuntimeConfig:
    return RuntimeConfig(
        environment=environment,
        environment_explicit=True,
        app_root=root,
        uploads_dir=root / "uploads",
        templates_dir=root / "templates",
        static_dir=root / "static",
        app_base_url="https://example.test",
        database_host="db.internal",
        database_port=5432,
        database_name="private_database",
        database_user="private_user",
    )


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql):
        assert sql == "SELECT 1 AS healthy"

    def fetchone(self):
        return {"healthy": 1}


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return _Cursor()


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_health_reports_runtime_environment_and_full_release_without_database_identity(
    monkeypatch, tmp_path, environment
):
    config = _config(environment, tmp_path)
    monkeypatch.delenv("QRFACILE_RELEASE_SHA", raising=False)
    monkeypatch.setattr(health_module, "get_runtime_config", lambda **_kwargs: config)
    monkeypatch.setattr(health_module, "pg", lambda: _Connection())
    monkeypatch.setattr(health_module.subprocess, "check_output", lambda *_args, **_kwargs: SHA)

    response = health_module.health()
    payload = json.loads(response.body)

    assert response.status_code == 200
    assert payload == {
        "status": "OK",
        "environment": environment,
        "database": "OK",
        "release": SHA,
    }
    assert "private_database" not in response.body.decode()
    assert "private_user" not in response.body.decode()


def test_release_lookup_uses_the_configured_application_root(monkeypatch, tmp_path):
    config = _config("staging", tmp_path)
    observed = {}

    def check_output(command, **kwargs):
        observed["command"] = command
        observed["cwd"] = kwargs["cwd"]
        return SHA

    monkeypatch.delenv("QRFACILE_RELEASE_SHA", raising=False)
    monkeypatch.setattr(health_module.subprocess, "check_output", check_output)

    assert health_module.get_release_revision(config) == SHA
    assert observed == {"command": ["git", "rev-parse", "HEAD"], "cwd": tmp_path}


def test_valid_explicit_release_sha_avoids_git_lookup(monkeypatch, tmp_path):
    config = _config("production", tmp_path)
    monkeypatch.setenv("QRFACILE_RELEASE_SHA", SHA.upper())
    monkeypatch.setattr(
        health_module.subprocess,
        "check_output",
        lambda *_args, **_kwargs: pytest.fail("Git must not run when the release SHA is explicit"),
    )

    assert health_module.get_release_revision(config) == SHA


def test_invalid_explicit_release_sha_fails_health_closed(monkeypatch, tmp_path):
    config = _config("staging", tmp_path)
    monkeypatch.setenv("QRFACILE_RELEASE_SHA", "short-or-untrusted")
    monkeypatch.setattr(health_module, "get_runtime_config", lambda **_kwargs: config)
    monkeypatch.setattr(health_module, "pg", lambda: pytest.fail("DB must not run"))

    response = health_module.health()

    assert response.status_code == 503
    assert json.loads(response.body) == {
        "status": "ERROR",
        "environment": "staging",
        "database": "ERROR",
        "release": "unavailable",
    }


def test_database_failure_keeps_release_identity_without_leaking_exception(monkeypatch, tmp_path):
    config = _config("production", tmp_path)
    monkeypatch.delenv("QRFACILE_RELEASE_SHA", raising=False)
    monkeypatch.setattr(health_module, "get_runtime_config", lambda **_kwargs: config)
    monkeypatch.setattr(health_module.subprocess, "check_output", lambda *_args, **_kwargs: SHA)
    monkeypatch.setattr(health_module, "pg", lambda: (_ for _ in ()).throw(RuntimeError("secret DSN")))

    response = health_module.health()
    payload = json.loads(response.body)

    assert response.status_code == 503
    assert payload == {
        "status": "ERROR",
        "environment": "production",
        "database": "ERROR",
        "release": SHA,
    }
    assert "secret DSN" not in response.body.decode()
