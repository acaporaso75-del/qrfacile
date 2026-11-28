from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_management_service_forces_studio_publish_false():
    text = (ROOT / "qrfacile_app" / "services" / "collaboration_management.py").read_text(encoding="utf-8")
    assert "can_publish=FALSE" in text
    assert "assign_studio_to_label" in text
    assert "clear_label_collaboration" in text
    assert "revoke_studio_connection" in text


def test_only_safe_label_mutation_routes_are_registered():
    safe = (ROOT / "qrfacile_app" / "collaboration_management_ui.py").read_text(encoding="utf-8")
    legacy = (ROOT / "qrfacile_app" / "label_acl_ui.py").read_text(encoding="utf-8")
    for route in ("acl/assign", "acl/clear", "management/set"):
        decorator = f'@router.post("/app/label/{{label_id}}/{route}")'
        assert safe.count(decorator) == 1
        assert decorator not in legacy
    assert "csrf_input(request)" in legacy
    assert 'name="profile" value="graphic"' in legacy


def test_sensitive_collaboration_posts_have_origin_check_and_audit():
    text = (ROOT / "qrfacile_app" / "collaboration_management_ui.py").read_text(encoding="utf-8")
    assert text.count("require_csrf_or_same_origin(request") >= 5
    for event in (
        "label_collaborator_assigned",
        "label_collaborator_removed",
        "studio_permissions_changed",
        "studio_winery_access_revoked",
    ):
        assert event in text


def test_studio_connection_mutations_have_one_canonical_route_and_csrf_fields():
    management = (ROOT / "qrfacile_app" / "collaboration_management_ui.py").read_text(encoding="utf-8")
    settings = (ROOT / "qrfacile_app" / "winery_settings_ui.py").read_text(encoding="utf-8")
    for route in ("/app/settings/studios/set", "/app/settings/studios/revoke"):
        assert management.count(f'@router.post("{route}")') == 1
        assert f'@router.post("{route}")' not in settings
        assert f'action="{route}"' in settings
    assert settings.count("{csrf_html}") == 2
    assert 'csrf_token: str = Form("")' in management


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
