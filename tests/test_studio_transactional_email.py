from pathlib import Path

from qrfacile_app import studio_area, studio_settings_ui


def test_studio_to_winery_invite_uses_central_sender(monkeypatch):
    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return False, "smtp_delivery_failed"

    monkeypatch.setattr(studio_area, "send_text_email", fake_send)
    result = studio_area._send_winery_invite_email(
        to_email="winery@example.test",
        invite_link="https://example.test/invite",
        studio_email="studio@example.test",
        recommended_pack_label="Start",
    )

    assert result == (False, "smtp_delivery_failed")
    assert captured["to_email"] == "winery@example.test"
    assert "studio@example.test" in captured["body"]
    assert "https://example.test/invite" in captured["body"]
    assert "Start" in captured["body"]


def test_winery_to_studio_invite_uses_central_sender(monkeypatch):
    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return True, ""

    monkeypatch.setattr(studio_settings_ui, "send_text_email", fake_send)
    result = studio_settings_ui._send_studio_invite_email(
        to_email="studio@example.test",
        invite_link="https://example.test/invite",
        winery_name="Cantina Test",
    )

    assert result == (True, "")
    assert captured["to_email"] == "studio@example.test"
    assert "Cantina Test" in captured["subject"]
    assert "https://example.test/invite" in captured["body"]


def test_studio_invite_modules_do_not_open_smtp_or_expose_transport_errors():
    for module in (studio_area, studio_settings_ui):
        text = Path(module.__file__).read_text(encoding="utf-8")
        assert "import smtplib" not in text
        assert "SMTP_SSL" not in text
        assert "return False, str(e)" not in text
