from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_recycling_guidance_catalog_contains_common_wine_packaging_codes():
    text = (ROOT / "qrfacile_app" / "recycling_guidance_ui.py").read_text(encoding="utf-8")
    for marker in (
        "GL 70",
        "GL 71",
        "GL 72",
        "FOR 51",
        "PAP 20",
        "PAP 21",
        "PAP 22",
        "FE 40",
        "ALU 41",
        "PET 1",
        "PP 5",
        "C/PAP 81",
        "C/PAP 84",
    ):
        assert marker in text


def test_recycling_guidance_keeps_custom_values_available():
    text = (ROOT / "qrfacile_app" / "recycling_guidance_ui.py").read_text(encoding="utf-8")
    assert "Altro materiale / codice personalizzato" in text
    assert "datalist" in text
    assert "input[name^=\"rec_\"]" in text
    assert "data-catalog-status" not in text  # status is attached through dataset, not trusted input


def test_guided_route_precedes_legacy_compliance_route():
    main = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    guided = main.index('include_router_safe("qrfacile_app.recycling_guidance_ui")')
    legacy = main.index('include_router_safe("qrfacile_app.wine_compliance_ui")')
    assert guided < legacy
