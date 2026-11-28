from __future__ import annotations

import os
import smtplib
import socket
import time
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


_sleep = time.sleep
_RETRY_DELAYS = (1.0, 3.0)


def send_email_message(message: EmailMessage) -> tuple[bool, str]:
    config = load_smtp_config()
    if config is None:
        return False, "smtp_not_configured"

    if not message.get("To") or not message.get("Subject"):
        return False, "smtp_message_invalid"
    if message.get("From"):
        del message["From"]
    message["From"] = config.sender

    for attempt in range(len(_RETRY_DELAYS) + 1):
        sending = False
        try:
            if config.port == 465:
                with smtplib.SMTP_SSL(config.host, config.port, timeout=25) as client:
                    client.login(config.username, config.password)
                    sending = True
                    client.send_message(message)
            else:
                with smtplib.SMTP(config.host, config.port, timeout=25) as client:
                    client.starttls()
                    client.login(config.username, config.password)
                    sending = True
                    client.send_message(message)
            return True, ""
        except smtplib.SMTPRecipientsRefused:
            return False, "smtp_recipient_refused"
        except (socket.gaierror, ConnectionRefusedError, TimeoutError, OSError) as exc:
            # Only connection problems before sending (e.g. intermittent DNS) are retried:
            # a message that may have left is never sent twice.
            if sending or isinstance(exc, smtplib.SMTPException) or attempt == len(_RETRY_DELAYS):
                return False, "smtp_delivery_failed"
            _sleep(_RETRY_DELAYS[attempt])
        except Exception:
            return False, "smtp_delivery_failed"
    return False, "smtp_delivery_failed"


def send_text_email(*, to_email: str, subject: str, body: str) -> tuple[bool, str]:
    message = EmailMessage()
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
    return send_email_message(message)
