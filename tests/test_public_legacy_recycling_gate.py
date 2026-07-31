from qrfacile_app.public import _label_missing, _public_gate_allows
from qrfacile_app.services.recycling_catalog import normalize_recycling_items
from qrfacile_app.services.wine_compliance_explainability import run_explainable_wine_compliance


def test_active_public_label_with_legacy_placeholders_is_consistently_blocked_as_missing():
    raw = {
        component: {"component": component, "product": "", "code": "-", "extra_code": "", "note": ""}
        for component in ("bottle", "box", "capsule", "closure", "label", "other")
    }
    recycle = normalize_recycling_items(raw)
    nutrition = {"energy_kj": 340, "energy_kcal": 9}
    missing = _label_missing("it", "Enolab srl", ["solfiti"], nutrition, list(recycle.values()))
    report = run_explainable_wine_compliance({
        "wine": {"wine_name": "DBN7MEVG"},
        "ingredients": [],
        "allergens": ["solfiti"],
        "nutrition": nutrition,
        "recycle": recycle,
        "meta": {"extra_ingredients": "Enolab srl"},
    })

    assert missing == ["riciclabilità"]
    assert _public_gate_allows("attiva", missing, report) is False
    assert any(item["rule_id"] == "QRF-ELABEL-NUT-003" and item["status"] == "WARNING" for item in report["results"])


def test_active_public_label_with_valid_recycling_can_pass_gate():
    recycle = {"bottle": {"product": "Vetro incolore", "code": "GL 70"}}
    nutrition = {"energy_kj": 340, "energy_kcal": 81}
    missing = _label_missing("it", "Uva", ["solfiti"], nutrition, list(recycle.values()))
    report = run_explainable_wine_compliance({
        "wine": {"wine_name": "Vino"}, "ingredients": ["Uva"], "allergens": ["solfiti"],
        "nutrition": nutrition, "recycle": recycle, "meta": {},
    })
    assert _public_gate_allows("attiva", missing, report) is True
