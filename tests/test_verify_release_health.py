from __future__ import annotations

import json
from email.message import Message

import pytest

from scripts import verify_release_health


SHA = "55a1d9abf59e4303f1571d89257031402a67b924"  # pragma: allowlist secret


class _Response:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()
        self.headers = Message()
        self.headers["Content-Type"] = "application/json; charset=utf-8"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self._body


def _payload(**changes):
    payload = {
        "status": "OK",
        "database": "OK",
        "environment": "staging",
        "release": SHA,
    }
    payload.update(changes)
    return payload


def test_verify_payload_requires_exact_environment_database_status_and_release():
    assert verify_release_health.verify_payload(
        _payload(), expected_environment="staging", expected_release=SHA
    ) == []

    errors = verify_release_health.verify_payload(
        _payload(status="ERROR", environment="production", release="not-versioned"),
        expected_environment="staging",
        expected_release=SHA,
    )
    assert len(errors) == 3
    assert any("status" in error for error in errors)
    assert any("environment" in error for error in errors)
    assert any("release" in error for error in errors)


def test_main_returns_success_only_for_the_exact_release(monkeypatch, capsys):
    monkeypatch.setattr(
        verify_release_health,
        "urlopen",
        lambda request, timeout: _Response(_payload()),
    )

    result = verify_release_health.main(
        [
            "--url",
            "http://127.0.0.1:8001/healthz",
            "--expected-environment",
            "staging",
            "--expected-release",
            SHA,
        ]
    )

    assert result == 0
    assert f"RELEASE_HEALTH_OK environment=staging release={SHA}" in capsys.readouterr().out


def test_main_rejects_a_runtime_mismatch(monkeypatch, capsys):
    monkeypatch.setattr(
        verify_release_health,
        "urlopen",
        lambda request, timeout: _Response(_payload(release="not-versioned")),
    )

    result = verify_release_health.main(
        [
            "--url",
            "http://127.0.0.1:8001/healthz",
            "--expected-environment",
            "staging",
            "--expected-release",
            SHA,
        ]
    )

    assert result == 1
    assert "RELEASE_HEALTH_MISMATCH release" in capsys.readouterr().err


@pytest.mark.parametrize("release", ["short", "g" * 40, "a" * 39])
def test_main_rejects_an_invalid_expected_sha(release):
    with pytest.raises(SystemExit) as exc:
        verify_release_health.main(
            [
                "--url",
                "http://127.0.0.1:8001/healthz",
                "--expected-environment",
                "staging",
                "--expected-release",
                release,
            ]
        )
    assert exc.value.code == 2
