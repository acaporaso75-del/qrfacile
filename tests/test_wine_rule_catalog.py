import json
from pathlib import Path

import pytest

from qrfacile_app.services.wine_compliance_engine import run_wine_compliance
from qrfacile_app.services.wine_rule_catalog import load_wine_rule_catalog, public_rule_catalog


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


def test_catalog_is_versioned_and_has_unique_rules():
    catalog = load_wine_rule_catalog()
    assert catalog.version
    assert len(catalog.rules) >= 8
    assert len(catalog.rules) == len(set(catalog.rules))
    assert catalog.score_weights["ERROR"] > catalog.score_weights["WARNING"]


def test_every_engine_result_is_registered_in_catalog():
    catalog = load_wine_rule_catalog()
    report = run_wine_compliance(_payload())
    unknown = {item["rule_id"] for item in report["results"] if item["rule_id"] not in catalog.rules}
    assert unknown == set()


def test_public_catalog_contains_governance_metadata():
    catalog = public_rule_catalog()
    assert catalog["catalog_version"]
    for rule in catalog["rules"]:
        assert rule["rule_id"]
        assert rule["domain"]
        assert rule["field"]
        assert isinstance(rule["legal_basis"], list)
        assert isinstance(rule["blocking"], bool)
        assert isinstance(rule["human_review_required"], bool)


def test_duplicate_rule_ids_are_rejected(tmp_path: Path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({
        "catalog_version": "test",
        "score_weights": {"PASS": 0, "WARNING": 35, "ERROR": 100},
        "rules": [
            {
                "rule_id": "DUP-001",
                "domain": "test",
                "title": "Test",
                "default_severity": "WARNING",
                "blocking": False,
                "field": "test",
                "legal_basis": [],
                "human_review_required": True,
                "active": True,
            },
            {
                "rule_id": "DUP-001",
                "domain": "test",
                "title": "Test duplicate",
                "default_severity": "ERROR",
                "blocking": True,
                "field": "test",
                "legal_basis": [],
                "human_review_required": True,
                "active": True,
            },
        ],
    }), encoding="utf-8")

    load_wine_rule_catalog.cache_clear()
    with pytest.raises(ValueError, match="duplicata"):
        load_wine_rule_catalog(path)
    load_wine_rule_catalog.cache_clear()
