from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_ALLOWED_SEVERITIES = {"PASS", "WARNING", "ERROR"}
_CATALOG_PATH = Path(__file__).resolve().parents[1] / "compliance_rules" / "wine_rules.json"


@dataclass(frozen=True)
class WineRuleDefinition:
    rule_id: str
    domain: str
    title: str
    default_severity: str
    blocking: bool
    field: str
    legal_basis: tuple[str, ...]
    human_review_required: bool
    active: bool


@dataclass(frozen=True)
class WineRuleCatalog:
    version: str
    score_weights: dict[str, int]
    rules: dict[str, WineRuleDefinition]

    def get(self, rule_id: str) -> WineRuleDefinition:
        try:
            return self.rules[rule_id]
        except KeyError as exc:
            raise KeyError(f"Regola wine compliance non censita: {rule_id}") from exc


def _required_text(raw: dict[str, Any], key: str) -> str:
    value = str(raw.get(key) or "").strip()
    if not value:
        raise ValueError(f"Campo obbligatorio mancante nel catalogo regole: {key}")
    return value


def _parse_rule(raw: dict[str, Any]) -> WineRuleDefinition:
    severity = _required_text(raw, "default_severity").upper()
    if severity not in _ALLOWED_SEVERITIES:
        raise ValueError(f"Severità non valida: {severity}")

    legal_basis = raw.get("legal_basis") or []
    if not isinstance(legal_basis, list):
        raise ValueError("legal_basis deve essere una lista")

    return WineRuleDefinition(
        rule_id=_required_text(raw, "rule_id"),
        domain=_required_text(raw, "domain"),
        title=_required_text(raw, "title"),
        default_severity=severity,
        blocking=bool(raw.get("blocking")),
        field=_required_text(raw, "field"),
        legal_basis=tuple(str(item).strip() for item in legal_basis if str(item).strip()),
        human_review_required=bool(raw.get("human_review_required", True)),
        active=bool(raw.get("active", True)),
    )


@lru_cache(maxsize=1)
def load_wine_rule_catalog(path: str | Path | None = None) -> WineRuleCatalog:
    catalog_path = Path(path) if path else _CATALOG_PATH
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))

    version = _required_text(raw, "catalog_version")
    weights = raw.get("score_weights") or {}
    score_weights = {severity: int(weights.get(severity, 0)) for severity in _ALLOWED_SEVERITIES}

    parsed: dict[str, WineRuleDefinition] = {}
    for item in raw.get("rules") or []:
        rule = _parse_rule(item)
        if rule.rule_id in parsed:
            raise ValueError(f"Regola duplicata nel catalogo: {rule.rule_id}")
        parsed[rule.rule_id] = rule

    if not parsed:
        raise ValueError("Il catalogo wine compliance non contiene regole")

    return WineRuleCatalog(version=version, score_weights=score_weights, rules=parsed)


def public_rule_catalog() -> dict[str, Any]:
    catalog = load_wine_rule_catalog()
    return {
        "catalog_version": catalog.version,
        "score_weights": dict(catalog.score_weights),
        "rules": [
            {
                "rule_id": rule.rule_id,
                "domain": rule.domain,
                "title": rule.title,
                "default_severity": rule.default_severity,
                "blocking": rule.blocking,
                "field": rule.field,
                "legal_basis": list(rule.legal_basis),
                "human_review_required": rule.human_review_required,
                "active": rule.active,
            }
            for rule in catalog.rules.values()
        ],
    }
