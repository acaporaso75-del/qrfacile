from __future__ import annotations

import os
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


def paypal_checkout_origin() -> str:
    mode = (os.getenv("PAYPAL_MODE") or "sandbox").strip().lower()
    return (
        "https://www.paypal.com"
        if mode == "live"
        else "https://www.sandbox.paypal.com"
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Apply conservative browser security headers to every response.

    The policy deliberately avoids third-party script origins. If an external
    provider is introduced, update the policy only after privacy/security review.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            f"form-action 'self' {paypal_checkout_origin()}; "
            "object-src 'none'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "connect-src 'self'",
        )

        if request.url.scheme == "https" or os.getenv("FORCE_HTTPS", "0") == "1":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        if request.url.path.startswith(("/admin", "/app", "/api")):
            response.headers.setdefault("Cache-Control", "no-store")

        return response
