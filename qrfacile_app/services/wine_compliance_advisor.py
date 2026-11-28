from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping

ADVISOR_VERSION = "2026.07.1"

_PRIORITY_ORDER = {"BLOCKING": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}
_DEFAULT_MINUTES = {"BLOCKING": 20, "HIGH": 15, "MEDIUM": 10, "INFO": 5}


@dataclass(frozen=True)
class AdvisorAction:
    rule_id: str
    priority: str
    title: str
    reason: str
    action: str
    field: str | None
    estimated_minutes: int
    blocking: bool
    human_review_required: bool
    knowledge_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        item = asdict(self)
        item["knowledge_ids"] = list(self.knowledge_ids)
        return item


def _priority(item: Mapping[str, Any]) -> str:
    status = str(item.get("status") or "").upper()
    blocking = bool(item.get("blocking"))
    if status == "ERROR" and blocking:
        return "BLOCKING"
    if status == "ERROR":
        return "HIGH"
    if status == "WARNING":
        return "MEDIUM"
    return "INFO"


def _estimated_minutes(item: Mapping[str, Any], priority: str) -> int:
    evidence = item.get("evidence") or {}
    affected = 1
    if isinstance(evidence, Mapping):
        for key in ("invalid_fields", "missing_fields", "components"):
            value = evidence.get(key)
            if isinstance(value, list) and value:
                affected = max(affected, len(value))
    return min(120, _DEFAULT_MINUTES[priority] + max(0, affected - 1) * 5)


def build_compliance_advice(report: Mapping[str, Any]) -> dict[str, Any]:
    actions: list[AdvisorAction] = []
    for item in report.get("results") or []:
        status = str(item.get("status") or "").upper()
        if status == "PASS":
            continue
        priority = _priority(item)
        actions.append(AdvisorAction(
            rule_id=str(item.get("rule_id") or ""),
            priority=priority,
            title=str(item.get("title") or item.get("rule_id") or "Controllo"),
            reason=str(item.get("explanation") or ""),
            action=str(item.get("remediation") or "Verificare il dato e documentare la revisione umana."),
            field=str(item.get("field")) if item.get("field") else None,
            estimated_minutes=_estimated_minutes(item, priority),
            blocking=bool(item.get("blocking")),
            human_review_required=bool(item.get("human_review_required")),
            knowledge_ids=tuple(str(value) for value in (item.get("knowledge_ids") or [])),
        ))

    actions.sort(key=lambda action: (_PRIORITY_ORDER[action.priority], action.rule_id))
    priority_counts = {name: 0 for name in _PRIORITY_ORDER}
    for action in actions:
        priority_counts[action.priority] += 1

    total_checks = sum(int(value or 0) for value in (report.get("counts") or {}).values())
    passed_checks = int((report.get("counts") or {}).get("PASS") or 0)
    completion = 100 if total_checks == 0 else round((passed_checks / total_checks) * 100)

    return {
        "advisor_version": ADVISOR_VERSION,
        "engine_version": report.get("engine_version"),
        "catalog_version": report.get("catalog_version"),
        "knowledge_version": report.get("knowledge_version"),
        "publishable": bool(report.get("publishable")),
        "score": int(report.get("score") or 0),
        "completion_percent": completion,
        "total_actions": len(actions),
        "estimated_total_minutes": sum(action.estimated_minutes for action in actions),
        "priority_counts": priority_counts,
        "next_action": actions[0].to_dict() if actions else None,
        "actions": [action.to_dict() for action in actions],
    }
