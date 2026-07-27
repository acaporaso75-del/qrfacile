from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.wine_compliance_replay import (
    compare_replays,
    create_and_persist_replay,
    get_replay,
    list_replays,
)
from qrfacile_app.ui_shell import esc, page
from qrfacile_app.wine_compliance_engine_ui import _load_payload

router = APIRouter(tags=["wine-compliance-replay"])


def _authorize_replay(request: Request, replay_id: str) -> tuple[dict, dict]:
    user = require_any_role(request, ("admin", "studio", "winery"))
    replay = get_replay(replay_id)
    if not replay:
        raise HTTPException(404, "Replay non trovato")
    _load_payload(int(replay["wine_id"]), user)
    return user, replay


def _serialize(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


@router.post("/api/wines/{wine_id}/compliance-replays", response_class=JSONResponse)
def create_compliance_replay(request: Request, wine_id: int, reason: str = Query("manual", max_length=120)):
    user = require_any_role(request, ("admin", "studio", "winery"))
    payload = _load_payload(wine_id, user)
    replay = create_and_persist_replay(
        payload,
        actor_user_id=int(user.get("id") or 0) or None,
        reason=reason,
    )
    return JSONResponse(_serialize(replay), status_code=201)


@router.get("/api/wines/{wine_id}/compliance-replays", response_class=JSONResponse)
def compliance_replay_list(request: Request, wine_id: int, limit: int = Query(100, ge=1, le=500)):
    user = require_any_role(request, ("admin", "studio", "winery"))
    _load_payload(wine_id, user)
    return JSONResponse({"wine_id": wine_id, "items": _serialize(list_replays(wine_id, limit=limit))})


@router.get("/api/compliance-replays/{replay_id}", response_class=JSONResponse)
def compliance_replay_detail(request: Request, replay_id: str):
    _, replay = _authorize_replay(request, replay_id)
    return JSONResponse(_serialize(replay))


@router.get("/api/compliance-replays/{replay_id}/verify", response_class=JSONResponse)
def compliance_replay_verify(request: Request, replay_id: str):
    _, replay = _authorize_replay(request, replay_id)
    return JSONResponse({
        "replay_id": replay_id,
        "integrity_valid": bool(replay.get("integrity_valid")),
        "content_hash": replay.get("content_hash"),
        "hash_algorithm": replay.get("hash_algorithm"),
    })


@router.get("/api/compliance-replays/{replay_id}/download")
def compliance_replay_download(request: Request, replay_id: str):
    _, replay = _authorize_replay(request, replay_id)
    content = json.dumps(_serialize(replay), ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="compliance-replay-{replay_id}.json"'},
    )


@router.get("/api/compliance-replays/compare/{left_replay_id}/{right_replay_id}", response_class=JSONResponse)
def compliance_replay_compare(request: Request, left_replay_id: str, right_replay_id: str):
    user, left = _authorize_replay(request, left_replay_id)
    _, right = _authorize_replay(request, right_replay_id)
    if int(left["wine_id"]) != int(right["wine_id"]):
        raise HTTPException(400, "È possibile confrontare solo replay dello stesso vino")
    _load_payload(int(left["wine_id"]), user)
    return JSONResponse(_serialize(compare_replays(left, right)))


def _history_html(wine_id: int, items: list[dict]) -> str:
    rows = []
    for item in items:
        valid = "Verificabile" if item.get("content_hash") else "Non verificabile"
        publishable = "Sì" if item.get("publishable") else "No"
        replay_id = str(item.get("replay_id") or "")
        rows.append(f"""
        <tr>
          <td>{esc(str(item.get('created_at') or ''))}</td>
          <td><code>{esc(replay_id)}</code><div class='rpHash'>{esc(str(item.get('content_hash') or ''))}</div></td>
          <td>{esc(str(item.get('score')))}</td>
          <td>{esc(publishable)}</td>
          <td>{esc(str(item.get('catalog_version') or ''))}<br><small>{esc(str(item.get('knowledge_version') or ''))}</small></td>
          <td>{esc(valid)}</td>
          <td><a class='btn' href='/api/compliance-replays/{esc(replay_id)}/download'>JSON</a></td>
        </tr>
        """)
    empty = "<tr><td colspan='7'>Nessun replay registrato.</td></tr>" if not rows else ""
    return f"""
    <style>
      .rpTable{{width:100%;border-collapse:collapse;background:var(--card)}}
      .rpTable th,.rpTable td{{border:1px solid var(--border);padding:10px;text-align:left;vertical-align:top}}
      .rpHash{{max-width:280px;overflow:hidden;text-overflow:ellipsis;font-size:11px;color:var(--muted)}}
      @media(max-width:900px){{.rpTable{{display:block;overflow:auto}}}}
    </style>
    <div class='card'>
      <div class='h1'>Compliance Replay</div>
      <div class='p'>Storico append-only delle verifiche del vino {wine_id}. Ogni snapshot conserva dati, evidenze, versioni e hash SHA-256.</div>
      <form method='post' action='/api/wines/{wine_id}/compliance-replays'>
        <button class='btn btn-primary' type='submit'>Crea replay adesso</button>
      </form>
    </div>
    <div class='card' style='margin-top:14px'>
      <table class='rpTable'>
        <thead><tr><th>Data</th><th>Replay e hash</th><th>Score</th><th>Pubblicabile</th><th>Versioni</th><th>Integrità</th><th>Export</th></tr></thead>
        <tbody>{''.join(rows)}{empty}</tbody>
      </table>
    </div>
    """


@router.get("/app/wine/{wine_id}/compliance-replays", response_class=HTMLResponse)
def compliance_replay_history(request: Request, wine_id: int):
    user = require_any_role(request, ("admin", "studio", "winery"))
    _load_payload(wine_id, user)
    body = _history_html(wine_id, list_replays(wine_id))
    return HTMLResponse(page(request, user, "Compliance Replay", body))
