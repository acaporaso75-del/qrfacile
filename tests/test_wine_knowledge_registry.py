from dataclasses import replace

from qrfacile_app.services.wine_compliance_explainability import run_explainable_wine_compliance
from qrfacile_app.services.wine_knowledge_registry import load_wine_knowledge_registry
from qrfacile_app.services.wine_rule_catalog import WineRuleCatalog, load_wine_rule_catalog
from qrfacile_app.services.wine_rule_validator import validate_wine_rule_catalog


def _payload():
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
        "recycle": {"bottle": {"code": "GL 70", "product": "Vetro"}},
        "meta": {},
    }


def test_knowledge_registry_is_versioned_and_structured():
    registry = load_wine_knowledge_registry()
    assert registry.version
    assert len(registry.entries) >= 6
    for entry in registry.entries.values():
        assert entry.knowledge_id
        assert entry.title
        assert entry.reference
        assert entry.summary
        assert entry.interpretation
        assert entry.status == "active"


def test_all_active_rules_link_to_existing_active_knowledge():
    catalog = load_wine_rule_catalog()
    knowledge = load_wine_knowledge_registry()
    report = validate_wine_rule_catalog(catalog, knowledge)
    assert report.ready is True
    assert report.issues == ()


def test_unknown_knowledge_link_is_rejected():
    catalog = load_wine_rule_catalog()
    knowledge = load_wine_knowledge_registry()
    rules = dict(catalog.rules)
    rules["QRF-PACK-001"] = replace(
        rules["QRF-PACK-001"],
        knowledge_ids=("KB-NOT-FOUND",),
    )
    invalid = WineRuleCatalog(
        version=catalog.version,
        score_weights=dict(catalog.score_weights),
        rules=rules,
    )
    report = validate_wine_rule_catalog(invalid, knowledge)
    assert any(issue.code == "unknown_knowledge_link" for issue in report.issues)


def test_explainable_report_contains_knowledge_and_versions():
    report = run_explainable_wine_compliance(_payload())
    assert report["catalog_version"]
    assert report["knowledge_version"]
    assert report["results"]
    for item in report["results"]:
        assert item["knowledge_ids"]
        assert item["knowledge"]
        assert item["knowledge"][0]["reference"]
        assert item["knowledge"][0]["interpretation"]
