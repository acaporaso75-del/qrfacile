from __future__ import annotations

from pathlib import Path

import pytest

from qrfacile_app.runtime_config import load_runtime_config


def _safe_staging_env(tmp_path: Path) -> dict[str, str]:
    root = tmp_path / "qrfacile-staging"
    for directory in (root, root / "uploads", root / "templates", root / "static"):
        directory.mkdir(parents=True, exist_ok=True)
    return {
        "APP_ENV": "staging",
        "APP_ROOT": str(root),
        "UPLOADS_DIR": str(root / "uploads"),
        "TEMPLATES_DIR": str(root / "templates"),
        "STATIC_DIR": str(root / "static"),
        "APP_BASE_URL": "https://staging.qrfacile.it",
        "DATABASE_URL": (
            "postgresql://qrfacile_staging_user:never-print-this-secret"
            "@192.168.1.143:5432/qrfacile_staging_db"
        ),
        "PAYPAL_MODE": "sandbox",
    }


def test_safe_staging_configuration_is_accepted(tmp_path):
    config = load_runtime_config(_safe_staging_env(tmp_path))

    assert config.environment == "staging"
    assert config.uploads_dir == (tmp_path / "qrfacile-staging" / "uploads").resolve()
    assert config.database_name == "qrfacile_staging_db"
    assert config.database_user == "qrfacile_staging_user"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APP_ROOT", "/opt/qrfacile"),
        ("UPLOADS_DIR", "/opt/qrfacile/uploads"),
        ("TEMPLATES_DIR", "/opt/qrfacile/templates"),
        ("STATIC_DIR", "/opt/qrfacile/static"),
    ],
)
def test_staging_rejects_every_production_path(tmp_path, name, value):
    environ = _safe_staging_env(tmp_path)
    environ[name] = value

    with pytest.raises(RuntimeError, match=name):
        load_runtime_config(environ)


def test_staging_rejects_production_origin_without_leaking_secret(tmp_path):
    environ = _safe_staging_env(tmp_path)
    environ["APP_BASE_URL"] = "https://qrfacile.it/"

    with pytest.raises(RuntimeError) as exc:
        load_runtime_config(environ)

    assert "origine produttiva" in str(exc.value)
    assert "never-print-this-secret" not in str(exc.value)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://qrfacile_staging_user:secret@192.168.1.143/qrfacile_db",  # pragma: allowlist secret
        "postgresql://qrfacile_user:secret@192.168.1.143/qrfacile_staging_db",  # pragma: allowlist secret
        "postgresql://qrfacile_staging_user:secret@127.0.0.1/qrfacile_staging_db",  # pragma: allowlist secret
    ],
)
def test_staging_rejects_production_or_unexpected_database_identity(
    tmp_path, database_url
):
    environ = _safe_staging_env(tmp_path)
    environ["DATABASE_URL"] = database_url

    with pytest.raises(RuntimeError) as exc:
        load_runtime_config(environ)

    assert "secret" not in str(exc.value)


def test_staging_markers_require_explicit_environment(tmp_path):
    environ = _safe_staging_env(tmp_path)
    del environ["APP_ENV"]

    with pytest.raises(RuntimeError, match="APP_ENV=staging"):
        load_runtime_config(environ)


def test_staging_rejects_upload_directory_outside_app_root(tmp_path):
    environ = _safe_staging_env(tmp_path)
    outside = tmp_path / "shared-uploads"
    outside.mkdir()
    environ["UPLOADS_DIR"] = str(outside)

    with pytest.raises(RuntimeError, match="contenuta in APP_ROOT"):
        load_runtime_config(environ)


def test_validation_only_parses_configuration_and_never_opens_network(tmp_path, monkeypatch):
    import socket

    contacted = []
    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: contacted.append(args))

    load_runtime_config(_safe_staging_env(tmp_path))

    assert contacted == []


@pytest.mark.parametrize("mode", ["live", "", "invalid"])
def test_staging_rejects_non_sandbox_paypal_mode(tmp_path, mode):
    environ = _safe_staging_env(tmp_path)
    environ["PAYPAL_MODE"] = mode

    with pytest.raises(RuntimeError, match="PAYPAL_MODE"):
        load_runtime_config(environ)


def test_production_may_use_live_paypal_mode(tmp_path):
    root = tmp_path / "production-app"
    for directory in (root, root / "uploads", root / "templates", root / "static"):
        directory.mkdir(parents=True, exist_ok=True)
    config = load_runtime_config({
        "APP_ENV": "production",
        "APP_ROOT": str(root),
        "UPLOADS_DIR": str(root / "uploads"),
        "TEMPLATES_DIR": str(root / "templates"),
        "STATIC_DIR": str(root / "static"),
        "APP_BASE_URL": "https://example.test",
        "DATABASE_URL": "postgresql://app:secret@db.example.test/app",  # pragma: allowlist secret
        "PAYPAL_MODE": "live",
    })
    assert config.environment == "production"
