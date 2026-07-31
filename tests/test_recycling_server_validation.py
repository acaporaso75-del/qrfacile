from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_server_validation_route_precedes_legacy_save_route():
    main = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    guard = main.index('include_router_safe("qrfacile_app.recycling_validation_ui")')
    legacy = main.index('include_router_safe("qrfacile_app.wine_compliance_ui")')
    assert guard < legacy


def test_server_validation_delegates_only_after_catalog_checks():
    text = (ROOT / "qrfacile_app" / "recycling_validation_ui.py").read_text(encoding="utf-8")
    validation = text.index("validate_recycling_items(recycle)")
    missing = text.index('validation["missing_codes"]')
    mismatches = text.index('validation["mismatches"]')
    delegate = text.index("return legacy_compliance_save")
    assert validation < missing < delegate
    assert validation < mismatches < delegate


def test_custom_codes_are_not_blocked_by_server_guard():
    text = (ROOT / "qrfacile_app" / "recycling_validation_ui.py").read_text(encoding="utf-8")
    assert 'validation["custom_codes"]' not in text
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
