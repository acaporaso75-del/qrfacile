from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping
from urllib.parse import quote


def get_uploads_dir() -> Path:
    root = os.getenv("UPLOADS_DIR") or os.path.join(os.getenv("APP_ROOT", "/opt/qrfacile"), "uploads")
    return Path(root).expanduser().resolve()


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


def asset_url(value: object, version: object = "") -> str:
    relative = normalize_asset_path(value)
    suffix = f"?v={quote(str(version))}" if str(version or "").strip() else ""
    return f"/uploads/{quote(relative, safe='/')}{suffix}"


def verify_saved_asset(paths: Mapping[str, object]) -> dict[str, Path]:
    verified: dict[str, Path] = {}
    for key, value in paths.items():
        target = asset_absolute_path(value)
        if not target.is_file() or not os.access(target, os.R_OK) or target.stat().st_size <= 0:
            raise OSError(f"Asset {key} non leggibile: {target}")
        verified[key] = target
    return verified
