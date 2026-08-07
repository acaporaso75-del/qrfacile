import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import qrfacile_app.export_qr_ui as package_ui


class _Cursor:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _Connection:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self, **_kwargs):
        return _Cursor()


@pytest.fixture
def send(monkeypatch):
    package_ui._recent_sends.clear()
    monkeypatch.setattr(package_ui, "_require_export_access", lambda _request, _wine_id: {"id": 7, "role": "winery"})
    monkeypatch.setattr(package_ui, "pg", lambda: _Connection())
    monkeypatch.setattr(package_ui, "_wine", lambda _cur, wine_id: {
        "wine_id": wine_id, "winery_id": 12, "winery_name": "Cantina Test",
        "wine_name": "Rosso", "lot": "L1", "slug": "rosso-l1",
    })
    monkeypatch.setattr(package_ui, "_build_zip_bundle", lambda *_args: b"zip")
    monkeypatch.setattr(package_ui, "_smtp_send_zip", lambda *_args: None)
    monkeypatch.setattr(package_ui, "audit_log", lambda *_args, **_kwargs: None)
    app = SimpleNamespace(state=SimpleNamespace(app_base_url="https://staging.example.test"))
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": ("127.0.0.1", 1), "app": app})

    def call(payload, wine_id=10):
        model = None if payload is None else package_ui.PackageSendRequest(**payload)
        result = package_ui.export_send(request, wine_id, model, "qrfacile")
        if hasattr(result, "body"):
            return result.status_code, json.loads(result.body)
        return 200, result

    return call


def test_empty_body_has_application_error_not_fastapi_validation_json(send):
    status, body = send(None)
    assert status == 400
    assert body == {"ok": False, "message": "Inserisci l’indirizzo email del destinatario"}
    assert "detail" not in body


def test_missing_to_email_has_clear_message(send):
    status, body = send({})
    assert status == 400
    assert body["message"] == "Inserisci l’indirizzo email del destinatario"


def test_invalid_email_is_rejected(send):
    status, body = send({"to_email": "non-valida"})
    assert status == 422
    assert body["message"] == "Inserisci un indirizzo email valido"


def test_valid_email_sends_package(send):
    status, body = send({"to_email": "destinatario@example.it"})
    assert status == 200
    assert body == {"ok": True, "message": "Pacchetti inviati correttamente"}


def test_unauthorized_user_is_rejected(send, monkeypatch):
    monkeypatch.setattr(package_ui, "_require_export_access", lambda *_args: (_ for _ in ()).throw(HTTPException(403, "Non autorizzato")))
    with pytest.raises(HTTPException) as exc:
        send({"to_email": "destinatario@example.it"})
    assert exc.value.status_code == 403


def test_package_from_another_winery_is_rejected_as_idor(send, monkeypatch):
    monkeypatch.setattr(package_ui, "_require_export_access", lambda *_args: (_ for _ in ()).throw(HTTPException(403, "Contesto cantina non corrisponde al lotto")))
    with pytest.raises(HTTPException) as exc:
        send({"to_email": "destinatario@example.it"}, wine_id=999)
    assert exc.value.status_code == 403


def test_duplicate_send_is_blocked(send):
    payload = {"to_email": "destinatario@example.it"}
    assert send(payload)[0] == 200
    status, body = send(payload)
    assert status == 409
    assert body["message"] == "Invio già effettuato. Attendi prima di riprovare."


def test_ui_uses_json_contract_and_never_renders_raw_fastapi_json():
    source = Path(package_ui.__file__).read_text(encoding="utf-8")
    assert "body: JSON.stringify({{to_email: toEmail}})" in source
    assert "'Content-Type': 'application/json'" in source
    assert "event.preventDefault()" in source
    assert "button.disabled = true" in source
    assert "let sending = false" in source
    assert "data.message || 'Invio non riuscito. Riprova.'" in source
    assert "message.textContent" in source
