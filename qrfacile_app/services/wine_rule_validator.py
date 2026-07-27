from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from qrfacile_app.services.wine_rule_catalog import WineRuleCatalog


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    rule_id: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    ready: bool
    issues: tuple[ValidationIssue, ...]
    rule_count: int
    active_rule_count: int
    blocking_rule_count: int

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "rule_count": self.rule_count,
            "active_rule_count": self.active_rule_count,
            "blocking_rule_count": self.blocking_rule_count,
            "issues": [
                {"code": issue.code, "message": issue.message, "rule_id": issue.rule_id}
                for issue in self.issues
            ],
        }


def _detect_cycles(catalog: WineRuleCatalog) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(rule_id: str, stack: list[str]) -> None:
        if rule_id in visited:
            return
        if rule_id in visiting:
            cycle_start = stack.index(rule_id) if rule_id in stack else 0
            cycle = stack[cycle_start:] + [rule_id]
            issues.append(ValidationIssue(
                code="dependency_cycle",
                rule_id=rule_id,
                message="Dipendenza circolare: " + " -> ".join(cycle),
            ))
            return

        visiting.add(rule_id)
        stack.append(rule_id)
        for dependency in catalog.rules[rule_id].dependencies:
            if dependency in catalog.rules:
                visit(dependency, stack)
        stack.pop()
        visiting.remove(rule_id)
        visited.add(rule_id)

    for rule_id in catalog.rules:
        visit(rule_id, [])
    return issues


def validate_wine_rule_catalog(catalog: WineRuleCatalog) -> ValidationReport:
    issues: list[ValidationIssue] = []

    required_weights = {"PASS", "WARNING", "ERROR"}
    missing_weights = required_weights.difference(catalog.score_weights)
    for severity in sorted(missing_weights):
        issues.append(ValidationIssue("missing_weight", f"Peso mancante per {severity}"))

    for severity, weight in catalog.score_weights.items():
        if weight < 0:
            issues.append(ValidationIssue("negative_weight", f"Peso negativo per {severity}"))

    if catalog.score_weights.get("PASS", 0) != 0:
        issues.append(ValidationIssue("pass_weight", "Il peso PASS deve essere zero"))
    if catalog.score_weights.get("ERROR", 0) <= catalog.score_weights.get("WARNING", 0):
        issues.append(ValidationIssue("weight_order", "Il peso ERROR deve superare WARNING"))

    for rule in catalog.rules.values():
        if rule.blocking and rule.default_severity != "ERROR":
            issues.append(ValidationIssue(
                "blocking_severity",
                "Una regola bloccante deve avere severità predefinita ERROR",
                rule.rule_id,
            ))
        if len(rule.dependencies) != len(set(rule.dependencies)):
            issues.append(ValidationIssue(
                "duplicate_dependency",
                "La regola contiene dipendenze duplicate",
                rule.rule_id,
            ))
        if rule.rule_id in rule.dependencies:
            issues.append(ValidationIssue(
                "self_dependency",
                "La regola non può dipendere da sé stessa",
                rule.rule_id,
            ))
        for dependency in rule.dependencies:
            if dependency not in catalog.rules:
                issues.append(ValidationIssue(
                    "unknown_dependency",
                    f"Dipendenza non censita: {dependency}",
                    rule.rule_id,
                ))
        if rule.default_severity == "ERROR" and rule.domain != "wine-core" and not rule.legal_basis:
            issues.append(ValidationIssue(
                "missing_legal_basis",
                "Regola ERROR priva di base normativa o tecnica documentata",
                rule.rule_id,
            ))

    issues.extend(_detect_cycles(catalog))

    return ValidationReport(
        ready=not issues,
        issues=tuple(issues),
        rule_count=len(catalog.rules),
        active_rule_count=sum(1 for rule in catalog.rules.values() if rule.active),
        blocking_rule_count=sum(1 for rule in catalog.rules.values() if rule.blocking),
    )


def assert_valid_wine_rule_catalog(catalog: WineRuleCatalog) -> None:
    report = validate_wine_rule_catalog(catalog)
    if report.ready:
        return
    details = "; ".join(
        f"{issue.code}{f'[{issue.rule_id}]' if issue.rule_id else ''}: {issue.message}"
        for issue in report.issues
    )
    raise ValueError(f"Catalogo wine compliance non valido: {details}")
