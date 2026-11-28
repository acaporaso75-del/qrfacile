from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Request, status


INTERNAL_TOKEN_ENV = "QRFACILE_INTERNAL_API_TOKEN"


def _extract_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "").strip()
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.headers.get("x-internal-token", "").strip()


def require_internal_token(request: Request) -> None:
    """Authenticate trusted machine-to-machine calls without user sessions."""
    configured = os.getenv(INTERNAL_TOKEN_ENV, "").strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API non configurata",
        )

    supplied = _extract_token(request)
    if not supplied or not secrets.compare_digest(supplied, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token interno non valido",
            headers={"WWW-Authenticate": "Bearer"},
        )
