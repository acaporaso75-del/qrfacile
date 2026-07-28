from pathlib import Path

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


def test_secure_publish_router_precedes_legacy_publish_router():
    text = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    safe = text.index('include_router_safe("qrfacile_app.secure_publish_ui")')
    legacy = text.index('include_router_safe("qrfacile_app.publish_routes")')
    assert safe < legacy


def test_override_request_is_audited():
    text = (ROOT / "qrfacile_app" / "secure_publish_ui.py").read_text(encoding="utf-8")
    assert "publish_override_requested" in text
    assert "missing_fields" in text
