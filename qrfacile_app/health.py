from __future__ import annotations

import os
import re
import subprocess

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from qrfacile_app.db import pg
from qrfacile_app.runtime_config import RuntimeConfig, get_runtime_config


router = APIRouter()

_FULL_GIT_SHA = re.compile(r"[0-9a-f]{40}")


def get_release_revision(config: RuntimeConfig) -> str:
    configured = (os.getenv("QRFACILE_RELEASE_SHA") or "").strip().lower()
    if configured:
        if not _FULL_GIT_SHA.fullmatch(configured):
            raise RuntimeError("QRFACILE_RELEASE_SHA non è uno SHA Git completo")
        return configured

    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=config.app_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip().lower()
    except Exception:
        return "not-versioned"
    return revision if _FULL_GIT_SHA.fullmatch(revision) else "not-versioned"


@router.get("/healthz")
def health():
    config = get_runtime_config(validate=False)
    try:
        release = get_release_revision(config)
        with pg() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS healthy")
                row = cur.fetchone()
        if not row or int(row.get("healthy") or 0) != 1:
            raise RuntimeError("Database health check non valido")

        return JSONResponse(
            status_code=200,
            content={
                "status": "OK",
                "environment": config.environment,
                "database": "OK",
                "release": release,
            },
        )
    except Exception:
        try:
            release = get_release_revision(config)
        except Exception:
            release = "unavailable"
        return JSONResponse(
            status_code=503,
            content={
                "status": "ERROR",
                "environment": config.environment,
                "database": "ERROR",
                "release": release,
            },
        )
