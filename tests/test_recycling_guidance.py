from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recycling_guidance_catalog_contains_wine_packaging_families():
    text = (ROOT / "qrfacile_app" / "recycling_guidance_ui.py").read_text(encoding="utf-8")
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
    text = (ROOT / "qrfacile_app" / "recycling_guidance_ui.py").read_text(encoding="utf-8")
    assert "Altro materiale / codice personalizzato" in text
    assert "Polimero biobased o compostabile" in text
    assert "datalist" in text
    assert 'input[name^="rec_"]' in text
    assert "Valore personalizzato" in text
    assert "verificarlo con il fornitore" in text


def test_catalog_has_component_specific_suggestions_and_authenticated_api():
    text = (ROOT / "qrfacile_app" / "recycling_guidance_ui.py").read_text(encoding="utf-8")
    assert '"components": ["bottle"' in text
    assert '"components": ["closure"' in text
    assert '"components": ["label"' in text
    assert '"components": ["box"' in text
    assert '/api/compliance/recycling-catalog' in text
    assert 'require_any_role(request, ("admin", "studio", "winery"))' in text


def test_guided_route_precedes_legacy_compliance_route():
    main = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    guided = main.index('include_router_safe("qrfacile_app.recycling_guidance_ui")')
    legacy = main.index('include_router_safe("qrfacile_app.wine_compliance_ui")')
    assert guided < legacy
