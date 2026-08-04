from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from starlette.requests import Request

from qrfacile_app import public, wine_flow_ui


def _request() -> Request:
    request = Request({"type": "http", "method": "GET", "path": "/app/wine/16/review", "query_string": b"", "headers": [], "client": ("127.0.0.1", 1)})
    request.state._auth_user = {"id": 10, "email": "owner@example.test", "role": "winery"}
    return request


def _context(*, published=False, slug="wine-16", images=True):
    assets = {"front": {}, "back": {}} if not images else {}
    return {
        "payload": {
            "wine": {"wine_name": "Vino Test", "winery_name": "Cantina Test"},
            "ingredients": ["uva"], "allergens": ["solfiti"],
            "nutrition": {"energy_kj": 300, "energy_kcal": 72},
            "recycle": {"bottle": {"product": "Bottiglia", "code": "GL 71"}},
        },
        "report": {"score": 100, "publishable": True, "results": []},
        "qr": {"slug": slug, "status": "attiva" if published else "bozza"},
        "assets": assets,
    }


@pytest.mark.parametrize("published, expected", [(False, "Stato: Pronto"), (True, "Stato: Pubblicato")])
def test_review_is_200_for_draft_and_published(monkeypatch, published, expected):
    monkeypatch.setattr(wine_flow_ui, "require_any_role", lambda *_args, **_kwargs: {"id": 10, "email": "owner@example.test", "role": "winery"})
    monkeypatch.setattr(wine_flow_ui, "_context", lambda *_args: _context(published=published))
    monkeypatch.setattr(wine_flow_ui, "csrf_input", lambda *_args: "")
    response = wine_flow_ui.review(_request(), 16)
    body = response.body.decode()
    assert response.status_code == 200
    assert expected in body
    assert 'src="/app/wine/16/preview"' in body
    assert "Apri anteprima in nuova scheda" in body


def test_review_without_slug_or_images_has_working_stable_preview_and_placeholders(monkeypatch):
    monkeypatch.setattr(wine_flow_ui, "require_any_role", lambda *_args, **_kwargs: {"id": 10, "email": "owner@example.test", "role": "winery"})
    monkeypatch.setattr(wine_flow_ui, "_context", lambda *_args: _context(slug="", images=False))
    monkeypatch.setattr(wine_flow_ui, "csrf_input", lambda *_args: "")
    response = wine_flow_ui.review(_request(), 16)
    body = response.body.decode()
    assert response.status_code == 200
    assert "/preview/\"" not in body
    assert 'src="/app/wine/16/preview"' in body
    assert "Immagine fronte non caricata" in body
    assert "Immagine retro non caricata" in body


def test_review_incomplete_data_uses_clear_placeholders(monkeypatch):
    ctx = _context(images=False)
    ctx["payload"]["nutrition"] = {}
    ctx["payload"]["recycle"] = {}
    monkeypatch.setattr(wine_flow_ui, "require_any_role", lambda *_args, **_kwargs: {"id": 10, "email": "owner@example.test", "role": "winery"})
    monkeypatch.setattr(wine_flow_ui, "_context", lambda *_args: ctx)
    monkeypatch.setattr(wine_flow_ui, "csrf_input", lambda *_args: "")
    body = wine_flow_ui.review(_request(), 16).body.decode()
    assert "Valori nutrizionali non completati" in body
    assert "Informazioni di riciclabilità mancanti" in body


def test_public_and_both_preview_routes_use_one_renderer(monkeypatch):
    calls = []
    monkeypatch.setattr(public, "_render_label_page", lambda request, slug="", **kwargs: calls.append((slug, kwargs)) or HTMLResponse("ok"))
    assert public.public_label(_request(), "slug-test").status_code == 200
    assert public.preview_label(_request(), "slug-test").status_code == 200
    assert public.preview_wine(_request(), 16).status_code == 200
    assert calls == [
        ("slug-test", {"preview": False}),
        ("slug-test", {"preview": True}),
        ("", {"preview": True, "wine_id": 16}),
    ]


def test_preview_headers_allow_only_same_origin_embedding_and_are_noindex():
    headers = public._preview_response_headers()
    assert headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in headers["Content-Security-Policy"]
    assert "noindex" in headers["X-Robots-Tag"]
    assert headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("status", [403, 404])
def test_preview_propagates_unauthorized_and_missing_wine_without_500(monkeypatch, status):
    monkeypatch.setattr(public, "_render_label_page", lambda *_args, **_kwargs: (_ for _ in ()).throw(HTTPException(status, "denied")))
    with pytest.raises(HTTPException) as exc:
        public.preview_wine(_request(), 999)
    assert exc.value.status_code == status

