from __future__ import annotations

from typing import Any, Mapping

from qrfacile_app.services.wine_compliance_engine import run_wine_compliance
from qrfacile_app.services.wine_knowledge_registry import load_wine_knowledge_registry
from qrfacile_app.services.wine_rule_catalog import load_wine_rule_catalog
from qrfacile_app.services.wine_rule_validator import assert_valid_wine_rule_catalog


def run_explainable_wine_compliance(payload: Mapping[str, Any]) -> dict[str, Any]:
    catalog = load_wine_rule_catalog()
    knowledge = load_wine_knowledge_registry()
    assert_valid_wine_rule_catalog(catalog, knowledge)

    report = run_wine_compliance(payload)
    enriched_results: list[dict[str, Any]] = []

    for item in report.get("results", []):
        enriched = dict(item)
        rule = catalog.get(str(item.get("rule_id") or ""))
        entries = [knowledge.get(knowledge_id) for knowledge_id in rule.knowledge_ids]
        enriched["knowledge_ids"] = list(rule.knowledge_ids)
        enriched["knowledge"] = [entry.to_dict() for entry in entries]
        enriched_results.append(enriched)

    return {
        **report,
        "catalog_version": catalog.version,
        "knowledge_version": knowledge.version,
        "results": enriched_results,
    }
