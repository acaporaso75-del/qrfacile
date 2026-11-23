"""Intermittent DNS on the server must not cancel a checkout or lose an invoice mail."""
from __future__ import annotations

import smtplib
import socket
from email.message import EmailMessage
from types import SimpleNamespace

import pytest
import requests

from qrfacile_app import paypal_ui
from qrfacile_app.services import transactional_email as te


class _Ok:
    status_code = 200

    def json(self):
        return {"access_token": "t"}


def test_paypal_post_retries_connection_errors_then_succeeds(monkeypatch):
    calls, sleeps = [], []

    def post(url, **kwargs):
        calls.append(url)
        if len(calls) < 3:
            raise requests.exceptions.ConnectionError("Failed to resolve 'api-m.sandbox.paypal.com'")
        return _Ok()

    monkeypatch.setattr(paypal_ui.requests, "post", post)
    monkeypatch.setattr(paypal_ui, "_sleep", sleeps.append)
    assert paypal_ui._paypal_post("https://x/v1/oauth2/token", timeout=30).status_code == 200
    assert len(calls) == 3 and len(sleeps) == 2


def test_paypal_post_gives_up_after_three_attempts(monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        raise requests.exceptions.ConnectTimeout("connect timeout")

    monkeypatch.setattr(paypal_ui.requests, "post", post)
    monkeypatch.setattr(paypal_ui, "_sleep", lambda s: None)
    with pytest.raises(requests.exceptions.ConnectTimeout):
        paypal_ui._paypal_post("https://x", timeout=30)
    assert len(calls) == 3


def test_paypal_post_never_retries_after_the_request_was_sent(monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        raise requests.exceptions.ReadTimeout("read timeout")

    monkeypatch.setattr(paypal_ui.requests, "post", post)
    monkeypatch.setattr(paypal_ui, "_sleep", lambda s: pytest.fail("no retry expected"))
    with pytest.raises(requests.exceptions.ReadTimeout):
        paypal_ui._paypal_post("https://x", timeout=30)
    assert len(calls) == 1


def test_all_paypal_calls_go_through_the_retry_helper():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "qrfacile_app" / "paypal_ui.py").read_text(encoding="utf-8")
    assert source.count("requests.post(") == 1  # only inside _paypal_post
    assert source.count("_paypal_post(") >= 5


def _config():
    return SimpleNamespace(host="smtp.example.test", port=587, username="u", password="p", sender="noreply@x")


def _message():
    message = EmailMessage()
    message["To"] = "a@example.test"
    message["Subject"] = "Test"
    message.set_content("x")
    return message


def test_email_retries_when_the_server_name_does_not_resolve(monkeypatch):
    attempts = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            attempts.append(host)
            if len(attempts) < 2:
                raise socket.gaierror(-3, "Temporary failure in name resolution")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def login(self, *a):
            pass

        def send_message(self, message):
            attempts.append("sent")

    monkeypatch.setattr(te, "load_smtp_config", _config)
    monkeypatch.setattr(te.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(te, "_sleep", lambda s: None)
    assert te.send_email_message(_message()) == (True, "")
    assert attempts == ["smtp.example.test", "smtp.example.test", "sent"]


def test_email_is_not_resent_after_sending_started(monkeypatch):
    attempts = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            attempts.append("connect")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            pass

        def login(self, *a):
            pass

        def send_message(self, message):
            raise smtplib.SMTPServerDisconnected("dropped")

    monkeypatch.setattr(te, "load_smtp_config", _config)
    monkeypatch.setattr(te.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(te, "_sleep", lambda s: pytest.fail("no retry after sending started"))
    assert te.send_email_message(_message()) == (False, "smtp_delivery_failed")
    assert attempts == ["connect"]
