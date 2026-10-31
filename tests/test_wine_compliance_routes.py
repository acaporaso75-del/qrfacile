from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from qrfacile_app import wine_compliance_engine_ui as engine_ui
from qrfacile_app import wine_compliance_replay_ui as replay_ui
from qrfacile_app.csrf_core import csrf_token_for_request


def _request(path: str, method: str = "GET", *, cookie: str = "") -> Request:
    headers = [(b"host", b"testserver")]
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    return Request({
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": headers,
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("testclient", 123),
    })


def _user(role: str = "winery") -> dict:
    return {
        "id": 42,
        "email": f"{role}@example.test",
        "role": role,
        "credits": {"available": 3},
    }


def _report(*, publishable: bool = False) -> dict:
    return {
        "engine_version": "engine-1",
        "catalog_version": "catalog-1",
        "knowledge_version": "knowledge-1",
        "score": 74,
        "publishable": publishable,
        "blocking_error_count": 1 if not publishable else 0,
        "counts": {"PASS": 2, "WARNING": 1, "ERROR": 1 if not publishable else 0},
        "results": [{
            "status": "ERROR" if not publishable else "PASS",
            "blocking": not publishable,
            "title": "Ingredienti obbligatori",
            "rule_id": "QRF-TEST-001",
            "version": "engine-1",
            "explanation": "Dato obbligatorio assente",
            "evidence": {"missing_fields": ["ingredients"]},
            "remediation": "Completare gli ingredienti",
            "knowledge": [],
        }],
    }


@pytest.mark.parametrize("wine_id", [16, 620])
def test_compliance_report_routes_return_200_for_requested_wines(monkeypatch, wine_id):
    monkeypatch.setattr(engine_ui, "require_any_role", lambda *_args: _user())
    monkeypatch.setattr(engine_ui, "_load_payload", lambda actual, _user: {"wine": {"wine_id": actual}})
    monkeypatch.setattr(engine_ui, "run_explainable_wine_compliance", lambda _payload: _report())
    response = engine_ui.compliance_report(_request(f"/app/wine/{wine_id}/compliance-report"), wine_id)
    body = response.body.decode()
    assert response.status_code == 200
    assert "Report di conformità" in body
    assert "Evidenza" in body
    assert "Pubblicabile" in body


def test_draft_wine_report_is_not_rejected_by_ui_route(monkeypatch):
    monkeypatch.setattr(engine_ui, "require_any_role", lambda *_args: _user())
    monkeypatch.setattr(engine_ui, "_load_payload", lambda *_args: {"wine": {"wine_id": 16, "status": "draft"}})
    monkeypatch.setattr(engine_ui, "run_explainable_wine_compliance", lambda _payload: _report())
    assert engine_ui.compliance_report(_request("/app/wine/16/compliance-report"), 16).status_code == 200


@pytest.mark.parametrize("wine_id", [16, 620])
def test_empty_history_returns_200_and_clear_message(monkeypatch, wine_id):
    monkeypatch.setattr(replay_ui, "require_any_role", lambda *_args: _user())
    monkeypatch.setattr(replay_ui, "_load_payload", lambda *_args: {})
    monkeypatch.setattr(replay_ui, "list_verified_replays", lambda _wine_id: [])
    response = replay_ui.compliance_replay_history(
        _request(f"/app/wine/{wine_id}/compliance-replays"), wine_id
    )
    assert response.status_code == 200
    assert "Non sono ancora presenti verifiche storiche." in response.body.decode()


def test_existing_history_shows_verified_integrity_detail_and_advanced_export(monkeypatch):
    replay_id = "11111111-1111-1111-1111-111111111111"
    summary = {
        "replay_id": replay_id,
        "created_at": datetime(2026, 8, 7, tzinfo=timezone.utc),
        "score": 91,
        "publishable": True,
        "catalog_version": "catalog-1",
        "content_hash": "a" * 64,
    }
    monkeypatch.setattr(replay_ui, "require_any_role", lambda *_args: _user())
    monkeypatch.setattr(replay_ui, "_load_payload", lambda *_args: {})
    monkeypatch.setattr(replay_ui, "list_verified_replays", lambda _wine_id: [{**summary, "integrity_valid": True}])
    body = replay_ui.compliance_replay_history(
        _request("/app/wine/16/compliance-replays"), 16
    ).body.decode()
    assert "Integra" in body
    assert "Apri dettaglio" in body
    assert "Dettagli tecnici" in body
    assert "Esporta JSON" in body


def test_snapshot_creation_redirects_without_raw_json(monkeypatch):
    created = []
    monkeypatch.setattr(replay_ui, "require_any_role", lambda *_args: _user())
    monkeypatch.setattr(replay_ui, "_load_payload", lambda *_args: {"wine": {"wine_id": 16}})
    monkeypatch.setattr(replay_ui, "create_and_persist_replay", lambda payload, **kwargs: created.append((payload, kwargs)) or {"replay_id": "saved"})
    request = _request(
        "/app/wine/16/compliance-replays",
        method="POST",
        cookie="qrfacile_session=test-session",
    )
    response = replay_ui.create_compliance_replay_from_page(
        request,
        16,
        csrf_token=csrf_token_for_request(request),
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/app/wine/16/compliance-replays?saved=1"
    assert response.headers.get("content-type") is None
    assert len(created) == 1


def test_snapshot_creation_rejects_missing_csrf_before_persistence(monkeypatch):
    persisted = []
    monkeypatch.setattr(replay_ui, "require_any_role", lambda *_args: _user())
    monkeypatch.setattr(
        replay_ui,
        "create_and_persist_replay",
        lambda *_args, **_kwargs: persisted.append(True),
    )
    with pytest.raises(HTTPException) as exc:
        replay_ui.create_compliance_replay_from_page(
            _request("/app/wine/16/compliance-replays", method="POST"),
            16,
            csrf_token="",
        )
    assert exc.value.status_code == 403
    assert persisted == []


def test_snapshot_api_rejects_missing_origin_or_csrf(monkeypatch):
    persisted = []
    monkeypatch.setattr(
        replay_ui,
        "create_and_persist_replay",
        lambda *_args, **_kwargs: persisted.append(True),
    )
    with pytest.raises(HTTPException) as exc:
        replay_ui.create_compliance_replay(
            _request("/api/wines/16/compliance-replays", method="POST"),
            16,
            reason="manual",
        )
    assert exc.value.status_code == 403
    assert persisted == []


@pytest.mark.parametrize("role", ["winery", "studio"])
def test_owner_and_assigned_studio_keep_acl_gate(monkeypatch, role):
    user = _user(role)
    seen = []
    monkeypatch.setattr(engine_ui, "require_any_role", lambda *_args: user)
    monkeypatch.setattr(engine_ui, "_load_payload", lambda wine_id, actual_user: seen.append((wine_id, actual_user)) or {})
    monkeypatch.setattr(engine_ui, "run_explainable_wine_compliance", lambda _payload: _report(publishable=True))
    assert engine_ui.compliance_report(_request("/app/wine/16/compliance-report"), 16).status_code == 200
    assert seen == [(16, user)]


def test_idor_denial_propagates_before_report_generation(monkeypatch):
    generated = []
    monkeypatch.setattr(engine_ui, "require_any_role", lambda *_args: _user("studio"))
    monkeypatch.setattr(engine_ui, "_load_payload", lambda *_args: (_ for _ in ()).throw(HTTPException(403, "Accesso al vino non autorizzato")))
    monkeypatch.setattr(engine_ui, "run_explainable_wine_compliance", lambda _payload: generated.append(True))
    with pytest.raises(HTTPException) as exc:
        engine_ui.compliance_report(_request("/app/wine/620/compliance-report"), 620)
    assert exc.value.status_code == 403
    assert generated == []


def test_history_idor_denial_happens_before_replay_listing(monkeypatch):
    listed = []
    monkeypatch.setattr(replay_ui, "require_any_role", lambda *_args: _user("studio"))
    monkeypatch.setattr(replay_ui, "_load_payload", lambda *_args: (_ for _ in ()).throw(HTTPException(403, "Accesso al vino non autorizzato")))
    monkeypatch.setattr(replay_ui, "list_verified_replays", lambda _wine_id: listed.append(True))
    with pytest.raises(HTTPException) as exc:
        replay_ui.compliance_replay_history(
            _request("/app/wine/620/compliance-replays"), 620
        )
    assert exc.value.status_code == 403
    assert listed == []


def test_snapshot_idor_denial_happens_before_persistence(monkeypatch):
    persisted = []
    monkeypatch.setattr(replay_ui, "require_csrf_or_same_origin", lambda *_args: None)
    monkeypatch.setattr(replay_ui, "require_any_role", lambda *_args: _user("studio"))
    monkeypatch.setattr(replay_ui, "_load_payload", lambda *_args: (_ for _ in ()).throw(HTTPException(403, "Accesso al vino non autorizzato")))
    monkeypatch.setattr(replay_ui, "create_and_persist_replay", lambda *_args, **_kwargs: persisted.append(True))
    with pytest.raises(HTTPException) as exc:
        replay_ui.create_compliance_replay_from_page(
            _request("/app/wine/620/compliance-replays", method="POST"),
            620,
            csrf_token="valid",
        )
    assert exc.value.status_code == 403
    assert persisted == []


def test_replay_authorization_reapplies_wine_acl(monkeypatch):
    replay_id = "33333333-3333-3333-3333-333333333333"
    user = _user("studio")
    replay = {"replay_id": replay_id, "wine_id": 620}
    checked = []
    monkeypatch.setattr(replay_ui, "require_any_role", lambda *_args: user)
    monkeypatch.setattr(replay_ui, "get_replay", lambda _replay_id: replay)
    monkeypatch.setattr(replay_ui, "_load_payload", lambda wine_id, actual_user: checked.append((wine_id, actual_user)) or {})
    assert replay_ui._authorize_replay(_request(f"/app/compliance-replays/{replay_id}"), replay_id) == (user, replay)
    assert checked == [(620, user)]


def test_replay_detail_reauthorizes_and_renders_without_exposing_hash_as_primary(monkeypatch):
    replay_id = "22222222-2222-2222-2222-222222222222"
    replay = {
        "replay_id": replay_id,
        "content_hash": "b" * 64,
        "integrity_valid": True,
        "snapshot": {"created_at": "2026-08-07T10:00:00+00:00", "report": _report(publishable=True)},
    }
    monkeypatch.setattr(replay_ui, "_authorize_replay", lambda *_args: (_user(), replay))
    response = replay_ui.compliance_replay_detail_page(
        _request(f"/app/compliance-replays/{replay_id}"), replay_id
    )
    body = response.body.decode()
    assert response.status_code == 200
    assert "Dettaglio verifica di conformità" in body
    assert "Dettagli tecnici" in body
