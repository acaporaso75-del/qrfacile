from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from qrfacile_app.csrf_core import require_csrf_or_same_origin

ROOT = Path(__file__).resolve().parents[1]


def test_csrf_core_binds_token_to_session():
    text = (ROOT / "qrfacile_app" / "csrf_core.py").read_text(encoding="utf-8")
    assert "hmac.new" in text
    assert "session_token" in text or "COOKIE" in text
    assert "secrets.compare_digest" in text
    assert "require_csrf_or_same_origin" in text


def test_secure_publish_blocks_studio_role_and_audits():
    text = (ROOT / "qrfacile_app" / "secure_publish_ui.py").read_text(encoding="utf-8")
    assert 'require_any_role(request, ("winery", "admin"))' in text
    assert 'action="wine_published"' in text or "wine_published_forced" in text
    assert 'action="wine_unpublished"' in text
    assert "create_and_persist_replay" in text
    assert "require_csrf_or_same_origin" in text
    assert "run_explainable_wine_compliance" in text
    assert 'if not report["publishable"]' in text
    assert "Override non necessario" in text


def test_secure_publish_router_precedes_legacy_publish_router():
    text = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    safe = text.index('include_router_safe("qrfacile_app.secure_publish_ui")')
    legacy = text.index('include_router_safe("qrfacile_app.publish_routes")')
    assert safe < legacy


def test_override_request_is_audited():
    text = (ROOT / "qrfacile_app" / "secure_publish_ui.py").read_text(encoding="utf-8")
    assert "publish_override_requested" in text
    assert "missing_fields" in text


def test_manual_post_without_csrf_or_origin_is_rejected():
    request = Request({
        "type": "http",
        "method": "POST",
        "scheme": "https",
        "path": "/app/wine/1/publish",
        "headers": [(b"host", b"example.test")],
        "query_string": b"",
        "server": ("example.test", 443),
    })

    with pytest.raises(HTTPException) as exc:
        require_csrf_or_same_origin(request)

    assert exc.value.status_code == 403


def test_studio_registration_requires_email_verification():
    source = (ROOT / "qrfacile_app" / "studio_register_routes.py").read_text(encoding="utf-8")
    assert "VALUES (%s,%s,'studio',%s,0,'modulare',0)" in source


def test_studio_publish_permission_is_not_offered_by_acl_ui():
    source = (ROOT / "qrfacile_app" / "label_acl_ui.py").read_text(encoding="utf-8")
    forbidden_control = 'name="' + "can_publish" + '"'
    assert forbidden_control not in source
