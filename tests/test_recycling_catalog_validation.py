from qrfacile_app.services.recycling_catalog import (
    CATALOG_VERSION,
    RECYCLING_CATALOG,
    find_by_code,
    get_recycling_suggestions,
    is_recycling_item_filled,
    normalize_recycling_items,
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


def _suggestion_codes(component):
    return [item["code"] for item in get_recycling_suggestions(component) if item["code"]]


def test_component_suggestions_start_with_explicit_priorities():
    assert _suggestion_codes("bottle")[:3] == ["GL 71", "GL 72", "GL 70"]
    assert _suggestion_codes("bottle")[0] != "PET 1"
    assert _suggestion_codes("closure")[0] == "FOR 51"
    assert _suggestion_codes("label")[0] == "PAP 22"
    assert _suggestion_codes("box")[0] == "PAP 20"


def test_all_compatible_catalog_items_remain_in_component_suggestions():
    for component in ("bottle", "closure", "capsule", "label", "box", "other"):
        expected = [item for item in RECYCLING_CATALOG if component in item.get("components", [])]
        actual = get_recycling_suggestions(component)
        assert {id(item) for item in actual} == {id(item) for item in expected}
        assert len(actual) == len(expected)


def test_known_consistent_codes_are_accepted():
    result = validate_recycling_items({
        "bottle": {"product": "Vetro verde", "code": "GL 71"},
        "closure": {"product": "Sughero", "code": "FOR 51"},
        "label": {"product": "Carta", "code": "PAP 22"},
    })
    assert result["all_known_and_consistent"] is True
    assert result["custom_codes"] == []
    assert result["mismatches"] == []


def test_six_legacy_dash_placeholders_are_one_absent_recycling_result():
    legacy = {
        component: {"product": "", "code": "-", "extra_code": "", "note": ""}
        for component in ("bottle", "box", "capsule", "closure", "label", "other")
    }
    assert normalize_recycling_items(legacy) == {}
    validation = validate_recycling_items(legacy)
    assert validation["component_count"] == 0
    assert validation["missing_codes"] == []

    report = run_explainable_wine_compliance(_payload(legacy))
    packaging = [item for item in report["results"] if item["rule_id"] == "QRF-PACK-001"]
    assert len(packaging) == 1
    assert packaging[0]["status"] == "WARNING"
    assert "assenti" in packaging[0]["title"].lower()


def test_any_real_value_makes_row_filled_and_subject_to_validation():
    row = {"product": "Sughero", "code": "-", "extra_code": "", "note": ""}
    assert is_recycling_item_filled(row) is True
    result = validate_recycling_items({"closure": row})
    assert result["missing_codes"] == ["closure"]


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
