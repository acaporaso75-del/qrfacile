from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_KNOWLEDGE_PATH = Path(__file__).resolve().parents[1] / "compliance_knowledge" / "wine_knowledge.json"
_ALLOWED_KINDS = {"regulation", "decision", "guidance", "faq", "technical-control", "best-practice"}
_ALLOWED_STATUSES = {"draft", "active", "deprecated", "archived"}


@dataclass(frozen=True)
class WineKnowledgeEntry:
    knowledge_id: str
    kind: str
    title: str
    issuer: str
    reference: str
    article: str
    annex: str
    source_url: str
    summary: str
    interpretation: str
    effective_from: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WineKnowledgeRegistry:
    version: str
    entries: dict[str, WineKnowledgeEntry]

    def get(self, knowledge_id: str) -> WineKnowledgeEntry:
        try:
            return self.entries[knowledge_id]
        except KeyError as exc:
            raise KeyError(f"Voce knowledge non censita: {knowledge_id}") from exc


def _required_text(raw: dict[str, Any], key: str) -> str:
    value = str(raw.get(key) or "").strip()
    if not value:
        raise ValueError(f"Campo knowledge obbligatorio mancante: {key}")
    return value


def _parse_entry(raw: dict[str, Any]) -> WineKnowledgeEntry:
    kind = _required_text(raw, "kind").lower()
    if kind not in _ALLOWED_KINDS:
        raise ValueError(f"Tipo knowledge non valido: {kind}")

    status = _required_text(raw, "status").lower()
    if status not in _ALLOWED_STATUSES:
        raise ValueError(f"Stato knowledge non valido: {status}")

    return WineKnowledgeEntry(
        knowledge_id=_required_text(raw, "knowledge_id"),
        kind=kind,
        title=_required_text(raw, "title"),
        issuer=_required_text(raw, "issuer"),
        reference=_required_text(raw, "reference"),
        article=str(raw.get("article") or "").strip(),
        annex=str(raw.get("annex") or "").strip(),
        source_url=str(raw.get("source_url") or "").strip(),
        summary=_required_text(raw, "summary"),
        interpretation=_required_text(raw, "interpretation"),
        effective_from=_required_text(raw, "effective_from"),
        status=status,
    )


@lru_cache(maxsize=1)
def load_wine_knowledge_registry(path: str | Path | None = None) -> WineKnowledgeRegistry:
    registry_path = Path(path) if path else _KNOWLEDGE_PATH
    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    version = _required_text(raw, "knowledge_version")

    parsed: dict[str, WineKnowledgeEntry] = {}
    for item in raw.get("entries") or []:
        entry = _parse_entry(item)
        if entry.knowledge_id in parsed:
            raise ValueError(f"Voce knowledge duplicata: {entry.knowledge_id}")
        parsed[entry.knowledge_id] = entry

    if not parsed:
        raise ValueError("Il registro knowledge vino non contiene voci")

    return WineKnowledgeRegistry(version=version, entries=parsed)


def public_wine_knowledge_registry() -> dict[str, Any]:
    registry = load_wine_knowledge_registry()
    return {
        "knowledge_version": registry.version,
        "entries": [entry.to_dict() for entry in registry.entries.values()],
    }
