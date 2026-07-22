from pathlib import Path
import subprocess

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from qrfacile_app.db import pg


router = APIRouter()


def get_git_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd="/opt/qrfacile-staging",
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "not-versioned"


@router.get("/healthz")
def health():
    try:
        with pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        current_database() AS database_name,
                        current_user AS database_user
                    """
                )
                row = cur.fetchone()

        return JSONResponse(
            status_code=200,
            content={
                "status": "OK",
                "environment": "staging",
                "database": row["database_name"],
                "db_user": row["database_user"],
                "git": get_git_revision(),
            },
        )

    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "ERROR",
                "environment": "staging",
                "database": None,
                "db_user": None,
                "git": get_git_revision(),
            },
        )
