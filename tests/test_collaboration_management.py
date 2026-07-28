from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_management_service_forces_studio_publish_false():
    text = (ROOT / "qrfacile_app" / "services" / "collaboration_management.py").read_text(encoding="utf-8")
    assert "can_publish=FALSE" in text
    assert "assign_studio_to_label" in text
    assert "clear_label_collaboration" in text
    assert "revoke_studio_connection" in text


def test_safe_routes_are_registered_before_legacy_acl():
    text = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    safe = text.index('include_router_safe("qrfacile_app.collaboration_management_ui")')
    legacy = text.index('include_router_safe("qrfacile_app.label_acl_ui")')
    assert safe < legacy


def test_sensitive_collaboration_posts_have_origin_check_and_audit():
    text = (ROOT / "qrfacile_app" / "collaboration_management_ui.py").read_text(encoding="utf-8")
    assert text.count("_same_origin(request)") >= 5
    for event in (
        "label_collaborator_assigned",
        "label_collaborator_removed",
        "studio_permissions_changed",
        "studio_winery_access_revoked",
    ):
        assert event in text


def test_access_center_has_one_clear_three_step_flow():
    text = (ROOT / "qrfacile_app" / "collaboration_access_ui.py").read_text(encoding="utf-8")
    assert "1. Collega" in text
    assert "2. Assegna" in text
    assert "3. Approva" in text
    assert "Mai consentita" in text
    assert "name='profile'" in text


def test_wine_access_requires_explicit_label_assignment():
    text = (ROOT / "qrfacile_app" / "services" / "collaboration_access.py").read_text(encoding="utf-8")
    assert "JOIN label_collaborators" in text
    assert "lc.active=TRUE" in text
    assert "sc.can_view=TRUE" in text
    assert "can_publish=False" in text
