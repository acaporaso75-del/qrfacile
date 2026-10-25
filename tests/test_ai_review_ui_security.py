from starlette.requests import Request

from qrfacile_app import ai_review_ui


def _request():
    return Request({
        "type": "http", "method": "GET", "scheme": "https", "path": "/admin/compliance/ai-review",
        "headers": [(b"host", b"example.test")], "client": ("127.0.0.1", 1),
    })


def test_ai_review_queue_escapes_registry_values_and_includes_csrf(monkeypatch):
    malicious = '<img src=x onerror="alert(1)">'
    monkeypatch.setattr(ai_review_ui, "require_any_role", lambda *_args, **_kwargs: {"id": 1, "role": "admin"})
    monkeypatch.setattr(ai_review_ui, "csrf_input", lambda _request: '<input name="csrf_token" value="test">')
    monkeypatch.setattr(ai_review_ui, "list_pending_ai_reviews", lambda: [{
        "id": 7,
        "created_at": "2026-10-25",
        "use_case": malicious,
        "provider": malicious,
        "model": "safe",
        "risk_classification": "limited",
        "contains_personal_data": False,
    }])
    response = ai_review_ui.ai_review_queue(_request())
    body = response.body.decode("utf-8")
    assert malicious not in body
    assert "&lt;img" in body
    assert 'name="csrf_token"' in body


def test_ai_review_schema_error_does_not_disclose_exception(monkeypatch):
    monkeypatch.setattr(ai_review_ui, "require_any_role", lambda *_args, **_kwargs: {"id": 1, "role": "admin"})
    monkeypatch.setattr(
        ai_review_ui,
        "list_pending_ai_reviews",
        lambda: (_ for _ in ()).throw(RuntimeError("database-host-secret")),
    )
    try:
        ai_review_ui.ai_review_queue(_request())
    except Exception as exc:
        assert "database-host-secret" not in str(exc)
        assert getattr(exc, "status_code", None) == 503
    else:
        raise AssertionError("schema error must return HTTP 503")


def test_prohibited_output_has_no_approval_control(monkeypatch):
    monkeypatch.setattr(ai_review_ui, "require_any_role", lambda *_args, **_kwargs: {"id": 1, "role": "admin"})
    monkeypatch.setattr(ai_review_ui, "csrf_input", lambda _request: '<input name="csrf_token" value="test">')
    monkeypatch.setattr(ai_review_ui, "list_pending_ai_reviews", lambda: [{
        "id": 9, "created_at": "2026-10-25", "use_case": "blocked", "provider": "internal",
        "model": "none", "risk_classification": "prohibited", "contains_personal_data": False,
    }])
    body = ai_review_ui.ai_review_queue(_request()).body.decode("utf-8")
    assert "Approvazione non consentita" in body
    assert 'value="approved"' not in body
    assert 'value="rejected"' in body
