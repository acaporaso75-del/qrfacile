from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import csrf_input, require_csrf_or_same_origin
from qrfacile_app.services.wine_compliance_replay import (
    compare_replays,
    create_and_persist_replay,
    get_replay,
    list_replays,
    list_verified_replays,
)
from qrfacile_app.ui_shell import esc, page
from qrfacile_app.wine_compliance_engine_ui import _load_payload, _report_html

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


def _display_datetime(value) -> str:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        return parsed.strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return str(value or "")


@router.post("/api/wines/{wine_id}/compliance-replays", response_class=JSONResponse)
def create_compliance_replay(request: Request, wine_id: int, reason: str = Query("manual", max_length=120)):
    require_csrf_or_same_origin(request)
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


def _history_html(wine_id: int, items: list[dict], *, csrf_html: str = "") -> str:
    rows = []
    for item in items:
        valid = "Integra" if item.get("integrity_valid") is True else "Non integra"
        publishable = "Sì" if item.get("publishable") else "No"
        replay_id = str(item.get("replay_id") or "")
        rows.append(f"""
        <tr>
          <td>{esc(_display_datetime(item.get('created_at')))}</td>
          <td>{esc(str(item.get('score')))}</td>
          <td>{esc(publishable)}</td>
          <td>{esc(str(item.get('catalog_version') or ''))}</td>
          <td>{esc(valid)}</td>
          <td><a class='btn' href='/app/compliance-replays/{esc(replay_id)}'>Apri dettaglio</a></td>
          <td><details><summary>Dettagli tecnici</summary><div><code>{esc(replay_id)}</code></div><div class='rpHash'>{esc(str(item.get('content_hash') or ''))}</div><a href='/api/compliance-replays/{esc(replay_id)}/download'>Esporta JSON</a></details></td>
        </tr>
        """)
    empty = "<tr><td colspan='7'>Non sono ancora presenti verifiche storiche.</td></tr>" if not rows else ""
    return f"""
    <style>
      .rpTable{{width:100%;border-collapse:collapse;background:var(--card)}}
      .rpTable th,.rpTable td{{border:1px solid var(--border);padding:10px;text-align:left;vertical-align:top}}
      .rpHash{{max-width:280px;overflow:hidden;text-overflow:ellipsis;font-size:11px;color:var(--muted)}}
      @media(max-width:900px){{.rpTable{{display:block;overflow:auto}}}}
    </style>
    <div class='card'>
      <div class='h1'>Storico verifiche di conformità</div>
      <div class='p'>Consulta le fotografie verificabili delle precedenti verifiche del vino {wine_id}.</div>
      <form method='post' action='/app/wine/{wine_id}/compliance-replays'>
        {csrf_html}
        <button class='btn btn-primary' type='submit'>Salva verifica corrente nello storico</button>
      </form>
      <div class='p'>Crea una fotografia verificabile dello stato di conformità attuale.</div>
    </div>
    <div class='card' style='margin-top:14px'>
      <table class='rpTable'>
        <thead><tr><th>Data</th><th>Score</th><th>Pubblicabile</th><th>Versione regole</th><th>Integrità</th><th>Dettaglio</th><th>Funzioni avanzate</th></tr></thead>
        <tbody>{''.join(rows)}{empty}</tbody>
      </table>
    </div>
    """


@router.get("/app/wine/{wine_id}/compliance-replays", response_class=HTMLResponse)
def compliance_replay_history(request: Request, wine_id: int, saved: int = 0):
    user = require_any_role(request, ("admin", "studio", "winery"))
    _load_payload(wine_id, user)
    items = list_verified_replays(wine_id)
    body = _history_html(wine_id, items, csrf_html=csrf_input(request))
    return HTMLResponse(page(
        title="Storico verifiche di conformità",
        subtitle="Fotografie verificabili delle verifiche precedenti",
        body_html=body,
        msg="Verifica salvata nello storico" if saved == 1 else "",
        user_email=str(user.get("email") or ""),
        role=str(user.get("role") or ""),
        credits=user.get("credits") if isinstance(user.get("credits"), dict) else None,
    ))


@router.post("/app/wine/{wine_id}/compliance-replays")
def create_compliance_replay_from_page(
    request: Request,
    wine_id: int,
    csrf_token: str = Form(""),
):
    require_csrf_or_same_origin(request, csrf_token)
    user = require_any_role(request, ("admin", "studio", "winery"))
    payload = _load_payload(wine_id, user)
    create_and_persist_replay(
        payload,
        actor_user_id=int(user.get("id") or 0) or None,
        reason="manual",
    )
    return RedirectResponse(
        f"/app/wine/{int(wine_id)}/compliance-replays?saved=1",
        status_code=303,
    )


@router.get("/app/compliance-replays/{replay_id}", response_class=HTMLResponse)
def compliance_replay_detail_page(request: Request, replay_id: str):
    user, replay = _authorize_replay(request, replay_id)
    snapshot = replay.get("snapshot") or {}
    report = snapshot.get("report") or {}
    created_at = snapshot.get("created_at") or replay.get("created_at") or ""
    try:
        verified_at = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        verified_at = None
    integrity = "Integra" if replay.get("integrity_valid") else "Non integra"
    if replay.get("integrity_valid") and report:
        report_html = _report_html(report, verified_at=verified_at)
    elif not replay.get("integrity_valid"):
        report_html = "<div class='card'><b>Integrità non verificata.</b> Il contenuto archiviato non viene mostrato.</div>"
    else:
        report_html = "<div class='card'>Report non disponibile.</div>"
    body = f"""
    <div class='card'>
      <div class='h1'>Dettaglio verifica di conformità</div>
      <div class='p'>Data: {esc(str(created_at))} · Integrità: <b>{esc(integrity)}</b></div>
      <details><summary>Dettagli tecnici</summary>
        <div>ID verifica: <code>{esc(str(replay.get('replay_id') or ''))}</code></div>
        <div>Hash: <code>{esc(str(replay.get('content_hash') or ''))}</code></div>
        <a href='/api/compliance-replays/{esc(replay_id)}/download'>Esporta JSON</a>
      </details>
    </div>
    {report_html}
    """
    return HTMLResponse(page(
        title="Dettaglio verifica di conformità",
        subtitle="Esito archiviato e controllo di integrità",
        body_html=body,
        user_email=str(user.get("email") or ""),
        role=str(user.get("role") or ""),
        credits=user.get("credits") if isinstance(user.get("credits"), dict) else None,
    ))
