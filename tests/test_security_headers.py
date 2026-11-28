from __future__ import annotations

import asyncio

import pytest
from starlette.requests import Request
from starlette.responses import Response

from qrfacile_app.security_middleware import SecurityHeadersMiddleware


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 443),
            "client": ("127.0.0.1", 4321),
            "scheme": "https",
        }
    )


def _response_for(path: str) -> Response:
    middleware = SecurityHeadersMiddleware(app=lambda *_args: None)

    async def call_next(_request):
        return Response("ok")

    return asyncio.run(middleware.dispatch(_request(path), call_next))


@pytest.mark.parametrize(
    "path",
    [
        "/admin",
        "/api/me/privacy-requests",
        "/app/billing",
        "/paypal/return",
        "/preview/example",
        "/reset-password",
        "/studio",
        "/studio/settings",
        "/verify-email/example",
    ],
)
def test_sensitive_surfaces_are_never_cached(path):
    assert _response_for(path).headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("path", ["/", "/wine", "/pricing", "/studio-public"])
def test_public_surfaces_are_not_accidentally_marked_no_store(path):
    assert "Cache-Control" not in _response_for(path).headers
