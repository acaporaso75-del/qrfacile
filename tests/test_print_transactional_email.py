from pathlib import Path

from qrfacile_app import send_print


def test_print_attachment_uses_central_sender(monkeypatch):
    captured = {}

    def fake_send(message):
        captured["message"] = message
        return True, ""

    monkeypatch.setattr(send_print, "send_email_message", fake_send)
    result = send_print._send_mail(
        "printer@example.test",
        "QR stampa",
        "In allegato",
        "qr.svg",
        b"<svg/>",
        "image/svg+xml",
    )

    assert result == (True, "")
    message = captured["message"]
    assert message["To"] == "printer@example.test"
    attachment = list(message.iter_attachments())[0]
    assert attachment.get_filename() == "qr.svg"
    assert attachment.get_content_type() == "image/svg+xml"


def test_print_module_has_no_parallel_smtp_client():
    text = Path(send_print.__file__).read_text(encoding="utf-8")
    assert "import smtplib" not in text
    assert "SMTP_SSL" not in text
