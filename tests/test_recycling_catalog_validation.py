from qrfacile_app.services.recycling_catalog import (
    CATALOG_VERSION,
    RECYCLING_CATALOG,
    find_by_code,
    validate_recycling_items,
)
from qrfacile_app.services.wine_compliance_explainability import run_explainable_wine_compliance


def _payload(recycle):
    return {
        "wine": {"wine_name": "Falanghina"},
        "ingredients": ["Uva", "Solfiti"],
        "allergens": ["Solfiti"],
        "nutrition": {
            "energy_kj": 300,
            "energy_kcal": 72,
            "fat": 0,
            "saturates": 0,
            "carbs": 2.4,
            "sugars": 0.8,
            "protein": 0,
            "salt": 0,
        },
        "recycle": recycle,
        "meta": {},
    }


def test_catalog_is_shared_versioned_and_contains_main_wine_components():
    assert CATALOG_VERSION
    assert len(RECYCLING_CATALOG) >= 30
    for code in ("GL 70", "GL 71", "GL 72", "FOR 51", "PAP 22", "ALU 41", "C/PAP 84"):
        assert find_by_code(code) is not None


def test_known_consistent_codes_are_accepted():
    result = validate_recycling_items({
        "bottle": {"product": "Vetro verde", "code": "GL 71"},
        "closure": {"product": "Sughero", "code": "FOR 51"},
        "label": {"product": "Carta", "code": "PAP 22"},
    })
    assert result["all_known_and_consistent"] is True
    assert result["custom_codes"] == []
    assert result["mismatches"] == []


def test_custom_code_is_preserved_but_flagged_for_review():
    report = run_explainable_wine_compliance(_payload({
        "closure": {"product": "Tappo innovativo", "code": "BIO 99"},
    }))
    packaging = next(item for item in report["results"] if item["rule_id"] == "QRF-PACK-001")
    assert packaging["status"] == "WARNING"
    assert packaging["evidence"]["custom_codes"][0]["code"] == "BIO 99"
    assert "personalizzati" in packaging["title"].lower()


def test_material_code_mismatch_blocks_publication():
    report = run_explainable_wine_compliance(_payload({
        "bottle": {"product": "Vetro verde", "code": "PAP 22"},
    }))
    packaging = next(item for item in report["results"] if item["rule_id"] == "QRF-PACK-001")
    assert packaging["status"] == "ERROR"
    assert packaging["blocking"] is True
    assert report["publishable"] is False
    assert packaging["evidence"]["mismatches"]
    assert "incongruenza" in packaging["title"].lower()


def test_filled_component_without_code_blocks_publication():
    report = run_explainable_wine_compliance(_payload({
        "closure": {"product": "Sughero", "code": ""},
    }))
    packaging = next(item for item in report["results"] if item["rule_id"] == "QRF-PACK-001")
    assert packaging["status"] == "ERROR"
    assert report["publishable"] is False


def test_recycling_validation_updates_score_and_report_metadata():
    good = run_explainable_wine_compliance(_payload({
        "bottle": {"product": "Vetro verde", "code": "GL 71"},
    }))
    custom = run_explainable_wine_compliance(_payload({
        "bottle": {"product": "Materiale speciale", "code": "X 999"},
    }))
    assert good["recycling_catalog_version"] == CATALOG_VERSION
    assert good["score"] > custom["score"]
    assert good["counts"]["PASS"] > custom["counts"]["PASS"]
