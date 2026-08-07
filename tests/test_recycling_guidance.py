from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _service_text() -> str:
    return (ROOT / "qrfacile_app" / "services" / "recycling_catalog.py").read_text(encoding="utf-8")


def _ui_text() -> str:
    return (ROOT / "qrfacile_app" / "recycling_guidance_ui.py").read_text(encoding="utf-8")


def test_recycling_catalog_contains_wine_packaging_families():
    text = _service_text()
    for marker in (
        "PET 1", "HDPE 2", "PVC 3", "LDPE 4", "PP 5", "PS 6", "OTHER 7",
        "PAP 20", "PAP 21", "PAP 22",
        "FE 40", "ALU 41", "FOR 50", "FOR 51", "COT 60", "TEX 61",
        "GL 70", "GL 71", "GL 72",
        "C/PAP 80", "C/PAP 81", "C/PAP 82", "C/PAP 83", "C/PAP 84", "C/PAP 85",
        "C/OTHER 90", "C/OTHER 91", "C/OTHER 92",
        "C/GL 95", "C/GL 96", "C/GL 97", "C/GL 98",
    ):
        assert marker in text


def test_recycling_guidance_keeps_custom_values_and_flags_them():
    service = _service_text()
    ui = _ui_text()
    assert "Altro materiale / codice personalizzato" in service
    assert "Polimero biobased o compostabile" in service
    assert "datalist" in ui
    assert 'input[name^="rec_"]' in ui
    assert "Valore personalizzato" in ui
    assert "verificarlo con il fornitore" in ui


def test_catalog_has_component_specific_suggestions_and_authenticated_api():
    service = _service_text()
    ui = _ui_text()
    assert '"bottle"' in service
    assert '"closure"' in service
    assert '"label"' in service
    assert '"box"' in service
    assert '/api/compliance/recycling-catalog' in ui
    assert 'require_any_role(request, ("admin", "studio", "winery"))' in ui
    assert "RECYCLING_CATALOG" in ui
    assert "from qrfacile_app.services.recycling_catalog import" in ui


def test_guidance_validates_before_save_and_can_restore_recommendation():
    ui = _ui_text()
    assert "Ripristina suggerimento" in ui
    assert "Materiale e codice non coincidono" in ui
    assert "non consigliato per" in ui
    assert "Correggere prima del salvataggio" in ui
    assert "event.preventDefault()" in ui
    assert "scrollIntoView" in ui
    assert "componentLabels" in ui
    assert "preferred[0]" not in ui
    assert "get_recycling_suggestions" in ui


def test_guidance_uses_separate_component_datalists_and_shared_api_suggestions():
    ui = _ui_text()
    assert 'qrf-recycling-materials-{component}' in ui
    assert 'qrf-recycling-codes-{component}' in ui
    assert '"suggestions"' in ui


def test_guided_route_precedes_legacy_compliance_route():
    main = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    guided = main.index('include_router_safe("qrfacile_app.recycling_guidance_ui")')
    legacy = main.index('include_router_safe("qrfacile_app.wine_compliance_ui")')
    assert guided < legacy
