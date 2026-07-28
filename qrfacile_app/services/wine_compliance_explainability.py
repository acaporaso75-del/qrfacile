from __future__ import annotations

from typing import Any, Mapping

from qrfacile_app.services.recycling_catalog import validate_recycling_items
from qrfacile_app.services.wine_compliance_engine import ERROR, PASS, WARNING, run_wine_compliance
from qrfacile_app.services.wine_knowledge_registry import load_wine_knowledge_registry
from qrfacile_app.services.wine_rule_catalog import load_wine_rule_catalog
from qrfacile_app.services.wine_rule_validator import assert_valid_wine_rule_catalog


def _apply_recycling_validation(report: dict[str, Any], payload: Mapping[str, Any], catalog) -> dict[str, Any]:
    validation = validate_recycling_items(payload.get("recycle") or {})
    results = [dict(item) for item in report.get("results", [])]

    for item in results:
        if item.get("rule_id") != "QRF-PACK-001":
            continue

        item["evidence"] = {**(item.get("evidence") or {}), **validation}
        if validation["missing_codes"]:
            item.update({
                "status": WARNING,
                "title": "Codici ambientali incompleti",
                "explanation": "Uno o più componenti non dispongono di un codice materiale valorizzato.",
                "remediation": "Completare i codici usando il catalogo guidato o il dato fornito dal produttore dell'imballaggio.",
            })
        elif validation["mismatches"]:
            item.update({
                "status": WARNING,
                "title": "Possibile incongruenza materiale–codice",
                "explanation": "Il codice selezionato non appare coerente con il materiale o con il tipo di componente indicato.",
                "remediation": "Controllare la scheda tecnica dell'imballaggio e correggere materiale o codice.",
            })
        elif validation["custom_codes"]:
            item.update({
                "status": WARNING,
                "title": "Codici personalizzati da verificare",
                "explanation": "Sono presenti codici non inclusi nel catalogo QRFacile corrente.",
                "remediation": "Conservare il codice comunicato dal fornitore e documentarne la verifica.",
            })
        elif validation["all_known_and_consistent"]:
            item.update({
                "status": PASS,
                "title": "Codici ambientali riconosciuti",
                "explanation": "I codici presenti sono riconosciuti dal catalogo e coerenti con i componenti indicati.",
                "remediation": None,
            })
        break

    counts = {PASS: 0, WARNING: 0, ERROR: 0}
    for item in results:
        counts[str(item.get("status") or "")] += 1

    penalty = sum(int(catalog.score_weights.get(str(item.get("status") or ""), 0)) for item in results)
    score = 100 if not results else max(0, round(100 - (penalty / len(results))))
    blocking_errors = [
        item for item in results
        if item.get("status") == ERROR and bool(item.get("blocking"))
    ]

    return {
        **report,
        "counts": counts,
        "score": score,
        "publishable": not blocking_errors,
        "blocking_error_count": len(blocking_errors),
        "recycling_catalog_version": validation["catalog_version"],
        "recycling_validation": validation,
        "results": results,
    }


def run_explainable_wine_compliance(payload: Mapping[str, Any]) -> dict[str, Any]:
    catalog = load_wine_rule_catalog()
    knowledge = load_wine_knowledge_registry()
    assert_valid_wine_rule_catalog(catalog, knowledge)

    report = _apply_recycling_validation(run_wine_compliance(payload), payload, catalog)
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
