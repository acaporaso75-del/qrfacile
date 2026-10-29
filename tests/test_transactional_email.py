from qrfacile_app.services import transactional_email
from scripts import check_transactional_email


def _environment(port: str = "465") -> dict[str, str]:
    return {
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": port,
        "SMTP_USER": "mailer@example.test",
        "SMTP_PASS": "test-only-placeholder",  # pragma: allowlist secret
        "SMTP_FROM": "QRFACILE <mailer@example.test>",
    }


class _Client:
    def __init__(self):
        self.started_tls = False
        self.message = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, _username, _password):
        return None

    def send_message(self, message):
        self.message = message


def test_config_is_fail_closed_and_does_not_fallback_on_invalid_port():
    assert transactional_email.load_smtp_config({}) is None
    assert transactional_email.load_smtp_config(_environment("invalid")) is None
    config = transactional_email.load_smtp_config(_environment())
    assert config is not None
    assert config.transport == "implicit_tls"


def test_send_uses_starttls_and_redacts_delivery_errors(monkeypatch):
    config = transactional_email.load_smtp_config(_environment("587"))
    client = _Client()
    monkeypatch.setattr(transactional_email, "load_smtp_config", lambda: config)
    monkeypatch.setattr(transactional_email.smtplib, "SMTP", lambda *_args, **_kwargs: client)

    sent, error = transactional_email.send_text_email(
        to_email="internal@example.test",
        subject="Prova QRFACILE",
        body="Messaggio tecnico",
    )
    assert sent is True and error == ""
    assert client.started_tls is True
    assert client.message["To"] == "internal@example.test"

    monkeypatch.setattr(
        transactional_email.smtplib,
        "SMTP",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("provider-sensitive")),
    )
    sent, error = transactional_email.send_text_email(
        to_email="internal@example.test",
        subject="Prova QRFACILE",
        body="Messaggio tecnico",
    )
    assert sent is False and error == "smtp_delivery_failed"
    assert "provider-sensitive" not in error


def test_attachment_message_uses_central_sender_and_sanitizes_recipient_error(monkeypatch):
    config = transactional_email.load_smtp_config(_environment())
    client = _Client()
    monkeypatch.setattr(transactional_email, "load_smtp_config", lambda: config)
    monkeypatch.setattr(transactional_email.smtplib, "SMTP_SSL", lambda *_args, **_kwargs: client)
    message = transactional_email.EmailMessage()
    message["From"] = "untrusted@example.test"
    message["To"] = "printer@example.test"
    message["Subject"] = "QR"
    message.set_content("Allegato")
    message.add_attachment(b"png", maintype="image", subtype="png", filename="qr.png")

    assert transactional_email.send_email_message(message) == (True, "")
    assert client.message["From"] == "QRFACILE <mailer@example.test>"
    assert list(client.message.iter_attachments())[0].get_filename() == "qr.png"

    def refuse(*_args, **_kwargs):
        raise transactional_email.smtplib.SMTPRecipientsRefused({})

    monkeypatch.setattr(transactional_email.smtplib, "SMTP_SSL", refuse)
    assert transactional_email.send_email_message(message) == (False, "smtp_recipient_refused")


def test_preflight_reports_only_transport_and_port(monkeypatch, capsys):
    config = transactional_email.load_smtp_config(_environment())
    monkeypatch.setattr(check_transactional_email, "load_smtp_config", lambda: config)

    assert check_transactional_email.main() == 0
    output = capsys.readouterr().out
    assert output.strip() == "TRANSACTIONAL_EMAIL_CONFIG_OK transport=implicit_tls port=465"
    assert "smtp.example.test" not in output
    assert "mailer@example.test" not in output


def test_preflight_script_can_run_from_its_documented_path():
    source = (check_transactional_email.PROJECT_ROOT / "scripts" / "check_transactional_email.py").read_text()
    assert 'sys.path.insert(0, str(PROJECT_ROOT))' in source
