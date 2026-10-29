from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Mapping


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    sender: str

    @property
    def transport(self) -> str:
        return "implicit_tls" if self.port == 465 else "starttls"


def load_smtp_config(environ: Mapping[str, str] | None = None) -> SmtpConfig | None:
    source = os.environ if environ is None else environ
    host = (source.get("SMTP_HOST") or "").strip()
    username = (source.get("SMTP_USER") or "").strip()
    password = (source.get("SMTP_PASS") or "").strip()
    sender = (
        (source.get("SMTP_FROM") or "").strip()
        or (source.get("FROM_EMAIL") or "").strip()
        or username
    )
    try:
        port = int((source.get("SMTP_PORT") or "465").strip())
    except (AttributeError, ValueError):
        return None
    if not all((host, username, password, sender)) or not 1 <= port <= 65535:
        return None
    return SmtpConfig(host, port, username, password, sender)


def send_email_message(message: EmailMessage) -> tuple[bool, str]:
    config = load_smtp_config()
    if config is None:
        return False, "smtp_not_configured"

    if not message.get("To") or not message.get("Subject"):
        return False, "smtp_message_invalid"
    if message.get("From"):
        del message["From"]
    message["From"] = config.sender

    try:
        if config.port == 465:
            with smtplib.SMTP_SSL(config.host, config.port, timeout=25) as client:
                client.login(config.username, config.password)
                client.send_message(message)
        else:
            with smtplib.SMTP(config.host, config.port, timeout=25) as client:
                client.starttls()
                client.login(config.username, config.password)
                client.send_message(message)
    except smtplib.SMTPRecipientsRefused:
        return False, "smtp_recipient_refused"
    except Exception:
        return False, "smtp_delivery_failed"
    return True, ""


def send_text_email(*, to_email: str, subject: str, body: str) -> tuple[bool, str]:
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    return send_email_message(message)
