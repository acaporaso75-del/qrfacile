from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_assignment_is_reversible_transactional_and_persisted():
    service = _read("qrfacile_app/services/collaboration_management.py")
    assert "FOR UPDATE" in service
    assert "old_studio" in service and "new_studio" in service
    assert "Verifica persistenza assegnazione studio fallita" in service
    assert "Verifica persistenza gestione diretta fallita" in service
    assert "SET active=FALSE" in service
    assert "DELETE FROM studio_clients" not in service.split("def clear_label_collaboration", 1)[1].split("def update_studio_connection_profile", 1)[0]


def test_manual_studio_id_is_checked_against_authorized_winery_link():
    service = _read("qrfacile_app/services/collaboration_management.py")
    assert "WHERE winery_id=%s AND studio_user_id=%s AND can_view=TRUE" in service
    assert "Solo la cantina proprietaria può gestire questa etichetta" in service


def test_mutations_are_post_only_and_audited_with_old_and_new_studio():
    ui = _read("qrfacile_app/collaboration_management_ui.py")
    assert ui.count('@router.post("/app/label/{label_id}') >= 3
    assert '@router.get("/app/label/{label_id}/acl/assign")' not in ui
    assert '"old_studio": result["old_studio"]' in ui
    assert '"new_studio": result["new_studio"]' in ui
    assert "_same_origin(request)" in ui


def test_ui_always_shows_current_state_and_clear_actions_without_bomb_icon():
    access_ui = _read("qrfacile_app/collaboration_access_ui.py")
    wine_ui = _read("qrfacile_app/wine_hub_ui.py")
    combined = access_ui + wine_ui
    assert "Gestione diretta della cantina" in combined
    assert "Studio assegnato:" in combined
    assert "Assegna uno studio" in access_ui
    assert "Cambia studio" in access_ui
    assert "Rimuovi studio assegnato" in access_ui
    assert "attuale" in access_ui
    assert "💣" not in combined


def test_wine_level_assignment_has_reload_verification_and_audit():
    wine_ui = _read("qrfacile_app/wine_hub_ui.py")
    assert "assigned_count" in wine_ui
    assert "active_count" in wine_ui
    assert "require_csrf_or_same_origin(request)" in wine_ui
    assert "wine_studio_assignment_changed" in wine_ui
    assert "wine_management_internal" in wine_ui
