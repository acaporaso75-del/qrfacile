from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_only_server_validated_compliance_save_route_is_registered():
    guard = (ROOT / "qrfacile_app" / "recycling_validation_ui.py").read_text(encoding="utf-8")
    legacy = (ROOT / "qrfacile_app" / "wine_compliance_ui.py").read_text(encoding="utf-8")
    route = '@router.post("/app/wine/{wine_id}/compliance/save")'
    assert guard.count(route) == 1
    assert route not in legacy
    assert 'require_csrf_or_same_origin(request, _text(form, "csrf_token"))' in guard


def test_compliance_forms_emit_csrf_and_mutations_validate_it():
    text = (ROOT / "qrfacile_app" / "wine_compliance_ui.py").read_text(encoding="utf-8")
    assert "csrf_html = csrf_input(request)" in text
    assert text.count("{csrf_html}") >= 4
    assert text.count("require_csrf_or_same_origin(request, csrf_token)") >= 2


def test_server_validation_persists_only_after_catalog_checks():
    text = (ROOT / "qrfacile_app" / "recycling_validation_ui.py").read_text(encoding="utf-8")
    validation = text.index("validate_recycling_items(recycle)")
    missing = text.index('validation["missing_codes"]')
    mismatches = text.index('validation["mismatches"]')
    persist = text.index("persist_recycling_component")
    persist_call = text.index("persist_recycling_component", persist + 1)
    assert validation < missing < persist_call
    assert validation < mismatches < persist_call
    assert "legacy_compliance_save" not in text


def test_custom_codes_are_not_blocked_by_server_guard():
    text = (ROOT / "qrfacile_app" / "recycling_validation_ui.py").read_text(encoding="utf-8")
    assert 'validation["custom_codes"]' in text
    assert "Codice personalizzato salvato" in text
    assert "is_recycling_item_filled(item)" in text


def test_all_legacy_form_fields_are_forwarded():
    text = (ROOT / "qrfacile_app" / "recycling_validation_ui.py").read_text(encoding="utf-8")
    for field in (
        "energy_kj",
        "energy_kcal",
        "fat",
        "saturates",
        "carbs",
        "sugars",
        "protein",
        "salt",
        "extra_ingredients",
        "story_text",
        "public_theme",
    ):
        assert f'"{field}"' in text
    for component in ("bottle", "closure", "capsule", "label", "box", "other"):
        assert f'f"rec_{{component}}_product"' in text
        assert f'f"rec_{{component}}_code"' in text
