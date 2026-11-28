from qrfacile_app.services.wine_compliance_engine import ERROR, PASS, WARNING, run_wine_compliance


def _complete_payload():
    return {
        "wine": {"wine_name": "Falanghina"},
        "ingredients": ["Uva", "Conservante: solfiti"],
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
        "recycle": {"bottle": {"code": "GL 70", "product": "Vetro"}},
        "meta": {"extra_ingredients": ""},
    }


def test_complete_payload_has_no_blocking_errors():
    report = run_wine_compliance(_complete_payload())
    assert report["publishable"] is True
    assert report["requires_human_review"] is True
    assert report["counts"][ERROR] == 0
    assert report["counts"][PASS] >= 5
    assert 0 <= report["score"] <= 100


def test_missing_required_content_blocks_publication():
    report = run_wine_compliance({
        "wine": {"wine_name": ""},
        "ingredients": [],
        "allergens": [],
        "nutrition": {},
        "recycle": {},
        "meta": {},
    })
    assert report["publishable"] is False
    assert report["counts"][ERROR] >= 3
    assert report["counts"][WARNING] >= 1


def test_energy_incoherence_is_explainable_warning():
    payload = _complete_payload()
    payload["nutrition"]["energy_kj"] = 300
    payload["nutrition"]["energy_kcal"] = 150
    report = run_wine_compliance(payload)
    warning = next(item for item in report["results"] if item["rule_id"] == "QRF-ELABEL-NUT-003")
    assert warning["status"] == WARNING
    assert warning["remediation"]
    assert warning["evidence"]["expected_kcal_technical"]


def test_negative_nutrition_value_is_error():
    payload = _complete_payload()
    payload["nutrition"]["sugars"] = -1
    report = run_wine_compliance(payload)
    assert report["publishable"] is False
    assert any(item["rule_id"] == "QRF-ELABEL-NUT-004" and item["status"] == ERROR for item in report["results"])


def test_every_result_is_versioned_and_explained():
    report = run_wine_compliance(_complete_payload())
    for item in report["results"]:
        assert item["rule_id"]
        assert item["version"] == report["engine_version"]
        assert item["status"] in {PASS, WARNING, ERROR}
        assert item["explanation"]
