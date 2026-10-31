from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_central_access_service_requires_both_general_and_label_permissions():
    text = (ROOT / "qrfacile_app" / "services" / "collaboration_access.py").read_text(encoding="utf-8")
    assert "studio_clients" in text
    assert "label_collaborators" in text
    assert "lc.active=TRUE" in text
    assert "general_view" in text
    assert "label_view" in text
    assert "can_publish=False" in text
    assert "require_label_permission" in text
    assert "require_wine_access" in text


def test_database_forces_studio_publish_off_and_cascades_revocation():
    text = (ROOT / "sql" / "2026_collaboration_access_hardening.sql").read_text(encoding="utf-8")
    assert text.startswith("BEGIN;")
    assert text.rstrip().endswith("COMMIT;")
    assert "NEW.can_publish := FALSE" in text
    assert "AFTER UPDATE OF can_view, can_edit, can_create OR DELETE ON studio_clients" in text
    assert "active=FALSE" in text
    assert "can_view=FALSE" in text
    assert "can_edit=FALSE" in text


def test_new_studio_accounts_are_not_auto_verified():
    text = (ROOT / "sql" / "2026_collaboration_access_hardening.sql").read_text(encoding="utf-8")
    assert "protect_new_studio_email_verification" in text
    assert "NEW.email_verified := 0" in text
    assert "BEFORE INSERT ON users" in text


def test_compliance_payload_uses_central_wine_access_gate():
    text = (ROOT / "qrfacile_app" / "wine_compliance_engine_ui.py").read_text(encoding="utf-8")
    assert "from qrfacile_app.services.collaboration_access import require_wine_access" in text
    assert 'require_wine_access(user, wine_id, "view")' in text
    assert "FROM studio_clients" not in text


def test_simplified_access_center_is_registered():
    main_text = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    ui_text = (ROOT / "qrfacile_app" / "collaboration_access_ui.py").read_text(encoding="utf-8")
    assert 'include_router_safe("qrfacile_app.collaboration_access_ui")' in main_text
    assert "/app/wine/{wine_id}/access-center" in ui_text
    assert "Nessuno studio può pubblicare" in ui_text
    assert "La pubblicazione resta sempre riservata" in ui_text


def test_studio_facing_surfaces_require_explicit_label_assignment():
    for relative in (
        "bulk_tools.py", "dashboard_ui.py", "label_acl_ui.py",
        "label_hub_ui.py", "public.py", "wine_hub_ui.py",
    ):
        text = (ROOT / "qrfacile_app" / relative).read_text(encoding="utf-8")
        assert "label_collaborators" in text, relative
        assert "studio_clients" in text, relative

    bulk = (ROOT / "qrfacile_app" / "bulk_tools.py").read_text(encoding="utf-8")
    assert "wine_labels_acl" not in bulk
    assert "wl.created_by_user_id =" not in bulk

    dashboard = (ROOT / "qrfacile_app" / "dashboard_ui.py").read_text(encoding="utf-8")
    assert "lc_scope.collaborator_user_id=%s" in dashboard
    assert "lc_scope.active=TRUE AND lc_scope.can_view=TRUE" in dashboard

    preview = (ROOT / "qrfacile_app" / "public.py").read_text(encoding="utf-8")
    assert "WHERE wl.wine_id=%s" in preview
    assert "lc.active=TRUE AND lc.can_view=TRUE AND sc.can_view=TRUE" in preview


def test_only_secure_invitation_routes_are_registered():
    legacy = (ROOT / "qrfacile_app" / "studio_settings_ui.py").read_text(encoding="utf-8")
    management = (ROOT / "qrfacile_app" / "invitation_management_ui.py").read_text(encoding="utf-8")
    acceptance = (ROOT / "qrfacile_app" / "invitation_acceptance_ui.py").read_text(encoding="utf-8")
    assert '@router.post("/app/settings/studios/invite")' not in legacy
    assert '@router.post("/app/invite/studio/accept/{token}")' not in legacy
    assert '@router.post("/app/settings/studios/invite")' in management
    assert '@router.post("/app/invite/studio/accept/{token}")' in acceptance
