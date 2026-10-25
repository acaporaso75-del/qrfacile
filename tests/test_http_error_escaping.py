import asyncio

from fastapi import HTTPException
from starlette.requests import Request

from qrfacile_app.main import http_exception_handler
from qrfacile_app import email_verification_ui


def _request():
    return Request({
        "type": "http", "method": "GET", "scheme": "https", "path": "/missing",
        "headers": [(b"host", b"example.test")], "client": ("127.0.0.1", 1),
    })


def test_http_exception_details_are_escaped_in_all_html_responses():
    malicious = '<script>alert("xss")</script>'
    for status_code in (404, 422, 500):
        response = asyncio.run(http_exception_handler(_request(), HTTPException(status_code, malicious)))
        body = response.body.decode("utf-8")
        assert malicious not in body
        assert "&lt;script&gt;" in body

    def reject(_token):
        raise HTTPException(400, malicious)

    original = email_verification_ui.verify_email
    email_verification_ui.verify_email = reject
    try:
        response = email_verification_ui.verify_email_page(_request(), "untrusted-token")
        body = response.body.decode("utf-8")
        assert malicious not in body
        assert "&lt;script&gt;" in body
    finally:
        email_verification_ui.verify_email = original
