from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.wine_knowledge_registry import (
    load_wine_knowledge_registry,
    public_wine_knowledge_registry,
)

router = APIRouter(tags=["wine-compliance-knowledge"])


@router.get("/api/admin/compliance/wine-knowledge", response_class=JSONResponse)
def wine_knowledge_registry_api(request: Request):
    require_any_role(request, ("admin",))
    return JSONResponse(public_wine_knowledge_registry())


@router.get("/api/compliance/wine-knowledge/{knowledge_id}", response_class=JSONResponse)
def wine_knowledge_entry_api(request: Request, knowledge_id: str):
    require_any_role(request, ("admin", "studio", "winery"))
    registry = load_wine_knowledge_registry()
    try:
        entry = registry.get(knowledge_id)
    except KeyError as exc:
        raise HTTPException(404, "Voce knowledge non trovata") from exc
    return JSONResponse({"knowledge_version": registry.version, "entry": entry.to_dict()})


@router.get("/api/compliance/wine-knowledge", response_class=JSONResponse)
def wine_knowledge_search_api(
    request: Request,
    q: str = Query("", max_length=160),
):
    require_any_role(request, ("admin", "studio", "winery"))
    registry = load_wine_knowledge_registry()
    needle = (q or "").strip().casefold()
    entries = list(registry.entries.values())
    if needle:
        entries = [
            entry for entry in entries
            if needle in " ".join((
                entry.knowledge_id,
                entry.title,
                entry.reference,
                entry.article,
                entry.summary,
                entry.interpretation,
            )).casefold()
        ]
    return JSONResponse({
        "knowledge_version": registry.version,
        "query": q,
        "count": len(entries),
        "entries": [entry.to_dict() for entry in entries],
    })
