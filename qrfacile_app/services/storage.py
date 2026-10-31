from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping
from urllib.parse import quote

from qrfacile_app.runtime_config import get_runtime_config


def get_uploads_dir() -> Path:
    return get_runtime_config(validate=False).uploads_dir


def get_templates_dir() -> Path:
    return get_runtime_config(validate=False).templates_dir


def normalize_asset_path(value: object) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if raw.startswith("/uploads/"):
        raw = raw[len("/uploads/"):]
    raw = raw.lstrip("/")
    if not raw or ".." in Path(raw).parts:
        raise ValueError("Percorso immagine non valido")
    return raw


def asset_absolute_path(value: object) -> Path:
    relative = normalize_asset_path(value)
    root = get_uploads_dir()
    target = (root / relative).resolve()
    if root not in target.parents:
        raise ValueError("Percorso immagine fuori dalla directory upload")
    return target


def versioned_upload_url(value: object, updated_at: object = "") -> str:
    relative = normalize_asset_path(value)
    suffix = f"?v={quote(str(updated_at))}" if str(updated_at or "").strip() else ""
    return f"/uploads/{quote(relative, safe='/')}{suffix}"


def asset_url(value: object, version: object = "") -> str:
    """Backward-compatible alias for callers outside the wine-assets flow."""
    return versioned_upload_url(value, version)


def verify_saved_asset(paths: Mapping[str, object]) -> dict[str, Path]:
    verified: dict[str, Path] = {}
    for key, value in paths.items():
        target = asset_absolute_path(value)
        if not target.is_file() or not os.access(target, os.R_OK) or target.stat().st_size <= 0:
            raise OSError(f"Asset {key} non leggibile: {target}")
        verified[key] = target
    return verified
