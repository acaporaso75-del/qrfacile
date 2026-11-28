import json
from dataclasses import replace
from pathlib import Path

import pytest

import qrfacile_app.services.wine_compliance_engine as engine_module
from qrfacile_app.services.wine_compliance_engine import ERROR, WARNING, run_wine_compliance
from qrfacile_app.services.wine_rule_catalog import (
    WineRuleCatalog,
    load_wine_rule_catalog,
    public_rule_catalog,
)


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


def _catalog_copy(*, score_weights=None, overrides=None):
    base = load_wine_rule_catalog()
    rules = dict(base.rules)
    for rule_id, changes in (overrides or {}).items():
        rules[rule_id] = replace(rules[rule_id], **changes)
    return WineRuleCatalog(
        version=base.version,
        score_weights=dict(score_weights or base.score_weights),
        rules=rules,
    )


def test_catalog_is_versioned_and_has_unique_rules():
    catalog = load_wine_rule_catalog()
    assert catalog.version
    assert len(catalog.rules) >= 8
    assert len(catalog.rules) == len(set(catalog.rules))
    assert catalog.score_weights["ERROR"] > catalog.score_weights["WARNING"]


def test_every_engine_result_is_registered_and_enriched():
    catalog = load_wine_rule_catalog()
    report = run_wine_compliance(_payload())
    unknown = {item["rule_id"] for item in report["results"] if item["rule_id"] not in catalog.rules}
    assert unknown == set()
    assert report["catalog_version"] == catalog.version
    for item in report["results"]:
        assert item["catalog_version"] == catalog.version
        assert item["domain"]
        assert isinstance(item["blocking"], bool)
        assert isinstance(item["legal_basis"], list)
        assert isinstance(item["human_review_required"], bool)


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


def test_score_uses_catalog_weights(monkeypatch):
    catalog = _catalog_copy(score_weights={"PASS": 0, "WARNING": 10, "ERROR": 50})
    monkeypatch.setattr(engine_module, "load_wine_rule_catalog", lambda: catalog)

    payload = _payload()
    payload["allergens"] = []
    report = run_wine_compliance(payload)
    expected_penalty = report["counts"][WARNING] * 10 + report["counts"][ERROR] * 50
    assert report["score"] == max(0, round(100 - expected_penalty / len(report["results"])))


def test_inactive_rule_is_not_executed(monkeypatch):
    catalog = _catalog_copy(overrides={"QRF-PACK-001": {"active": False}})
    monkeypatch.setattr(engine_module, "load_wine_rule_catalog", lambda: catalog)

    report = run_wine_compliance(_payload())
    assert all(item["rule_id"] != "QRF-PACK-001" for item in report["results"])


def test_only_blocking_errors_stop_publication(monkeypatch):
    catalog = _catalog_copy(overrides={"QRF-CORE-001": {"blocking": False}})
    monkeypatch.setattr(engine_module, "load_wine_rule_catalog", lambda: catalog)

    payload = _payload()
    payload["wine"]["wine_name"] = ""
    report = run_wine_compliance(payload)
    identity = next(item for item in report["results"] if item["rule_id"] == "QRF-CORE-001")
    assert identity["status"] == ERROR
    assert identity["blocking"] is False
    assert report["publishable"] is True
    assert report["blocking_error_count"] == 0


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
