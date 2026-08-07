from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote, urlsplit


PRODUCTION_ROOT = Path("/opt/qrfacile").resolve(strict=False)
PRODUCTION_ORIGINS = {"https://qrfacile.it", "https://www.qrfacile.it"}
STAGING_DB_HOST = "192.168.1.143"
STAGING_DB_NAME = "qrfacile_staging_db"
STAGING_DB_USER = "qrfacile_staging_user"


@dataclass(frozen=True)
class RuntimeConfig:
    environment: str
    environment_explicit: bool
    app_root: Path
    uploads_dir: Path
    templates_dir: Path
    static_dir: Path
    app_base_url: str
    database_host: str
    database_port: int | None
    database_name: str
    database_user: str


def _clean(value: object) -> str:
    return str(value or "").strip()


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _environment(source: Mapping[str, str]) -> tuple[str, bool]:
    raw = _clean(source.get("APP_ENV") or source.get("ENVIRONMENT")).lower()
    aliases = {
        "prod": "production",
        "production": "production",
        "stage": "staging",
        "staging": "staging",
        "dev": "development",
        "development": "development",
        "test": "test",
    }
    if not raw:
        return "production", False
    if raw not in aliases:
        raise RuntimeError(f"Ambiente applicativo non riconosciuto: {raw!r}")
    return aliases[raw], True


def _database_identity(database_url: str) -> tuple[str, int | None, str, str]:
    if not database_url:
        return "", None, "", ""
    try:
        parsed = urlsplit(database_url)
        host = parsed.hostname or ""
        port = parsed.port
        name = unquote(parsed.path.lstrip("/"))
        user = unquote(parsed.username or "")
    except (TypeError, ValueError) as exc:
        raise RuntimeError("DATABASE_URL non valida; credenziali non visualizzate") from exc
    return host, port, name, user


def _is_production_path(path: Path) -> bool:
    return path == PRODUCTION_ROOT or PRODUCTION_ROOT in path.parents


def _normalised_origin(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise RuntimeError("APP_BASE_URL non valida") from exc
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError("APP_BASE_URL deve essere un URL assoluto")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def load_runtime_config(
    environ: Mapping[str, str] | None = None,
    *,
    validate: bool = True,
) -> RuntimeConfig:
    source = os.environ if environ is None else environ
    environment, environment_explicit = _environment(source)

    app_root_raw = _clean(source.get("APP_ROOT")) or "/opt/qrfacile"
    app_root = _path(app_root_raw)
    uploads_dir = _path(_clean(source.get("UPLOADS_DIR")) or str(app_root / "uploads"))
    templates_dir = _path(_clean(source.get("TEMPLATES_DIR")) or str(app_root / "templates"))
    static_dir = _path(_clean(source.get("STATIC_DIR")) or str(app_root / "static"))
    app_base_url = _clean(source.get("APP_BASE_URL")).rstrip("/")
    database_url = _clean(source.get("DATABASE_URL") or source.get("QRFACILE_DB_DSN"))
    database_host, database_port, database_name, database_user = _database_identity(
        database_url
    )

    config = RuntimeConfig(
        environment=environment,
        environment_explicit=environment_explicit,
        app_root=app_root,
        uploads_dir=uploads_dir,
        templates_dir=templates_dir,
        static_dir=static_dir,
        app_base_url=app_base_url,
        database_host=database_host,
        database_port=database_port,
        database_name=database_name,
        database_user=database_user,
    )
    if validate:
        validate_runtime_config(config, source)
    return config


def validate_runtime_config(
    config: RuntimeConfig,
    source: Mapping[str, str] | None = None,
) -> None:
    values = os.environ if source is None else source
    errors: list[str] = []

    staging_markers = (
        "staging" in config.app_root.name.lower()
        or config.database_name == STAGING_DB_NAME
        or config.database_user == STAGING_DB_USER
    )
    if staging_markers and not config.environment_explicit:
        errors.append("APP_ENV=staging deve essere dichiarato esplicitamente")

    if config.environment == "staging":
        required = (
            "APP_ROOT",
            "UPLOADS_DIR",
            "TEMPLATES_DIR",
            "STATIC_DIR",
            "APP_BASE_URL",
            "DATABASE_URL",
            "PAYPAL_MODE",
        )
        missing = [name for name in required if not _clean(values.get(name))]
        if missing:
            errors.append("configurazione staging incompleta: " + ", ".join(missing))

        for label, path in (
            ("APP_ROOT", config.app_root),
            ("UPLOADS_DIR", config.uploads_dir),
            ("TEMPLATES_DIR", config.templates_dir),
            ("STATIC_DIR", config.static_dir),
        ):
            if _is_production_path(path):
                errors.append(f"{label} punta a un percorso produttivo: {path}")
            if not path.is_dir():
                errors.append(f"{label} non è una directory leggibile: {path}")

        for label, path in (
            ("UPLOADS_DIR", config.uploads_dir),
            ("TEMPLATES_DIR", config.templates_dir),
            ("STATIC_DIR", config.static_dir),
        ):
            if config.app_root not in path.parents:
                errors.append(f"{label} deve essere contenuta in APP_ROOT")

        try:
            origin = _normalised_origin(config.app_base_url)
        except RuntimeError as exc:
            errors.append(str(exc))
        else:
            if origin in PRODUCTION_ORIGINS:
                errors.append("APP_BASE_URL staging non può usare l'origine produttiva")

        if config.database_name == "qrfacile_db":
            errors.append("DATABASE_URL staging punta al database produttivo qrfacile_db")
        elif config.database_name != STAGING_DB_NAME:
            errors.append(f"database staging inatteso: {config.database_name or '<assente>'}")

        if config.database_user == "qrfacile_user":
            errors.append("DATABASE_URL staging usa l'utente produttivo qrfacile_user")
        elif config.database_user != STAGING_DB_USER:
            errors.append(f"utente database staging inatteso: {config.database_user or '<assente>'}")

        if config.database_host != STAGING_DB_HOST:
            errors.append(f"host database staging inatteso: {config.database_host or '<assente>'}")
        if config.database_port not in (None, 5432):
            errors.append(f"porta database staging inattesa: {config.database_port}")

        paypal_mode = _clean(values.get("PAYPAL_MODE")).lower()
        if paypal_mode != "sandbox":
            errors.append("PAYPAL_MODE staging deve essere sandbox")

    if errors:
        raise RuntimeError("Configurazione runtime non sicura: " + "; ".join(errors))


def get_runtime_config(*, validate: bool = True) -> RuntimeConfig:
    return load_runtime_config(validate=validate)
