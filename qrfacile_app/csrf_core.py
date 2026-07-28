from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from fastapi import HTTPException, Request

from qrfacile_app.auth_core import COOKIE

CSRF_FIELD = "csrf_token"
CSRF_HEADER = "x-csrf-token"


def _secret() -> bytes:
    configured = (os.getenv("CSRF_SECRET") or os.getenv("SESSION_SECRET") or "").strip()
    if not configured:
        configured = "qrfacile-development-csrf-secret-change-in-production"
    return configured.encode("utf-8")


def csrf_token_for_request(request: Request) -> str:
    session_token = request.cookies.get(COOKIE) or "anonymous"
    return hmac.new(_secret(), session_token.encode("utf-8"), hashlib.sha256).hexdigest()


def csrf_input(request: Request) -> str:
    token = csrf_token_for_request(request)
    return f'<input type="hidden" name="{CSRF_FIELD}" value="{token}">'


def require_csrf(request: Request, supplied: str | None = None) -> None:
    expected = csrf_token_for_request(request)
    candidate = (supplied or request.headers.get(CSRF_HEADER) or "").strip()
    if not candidate or not secrets.compare_digest(candidate, expected):
        raise HTTPException(403, "Richiesta non valida o sessione scaduta")
