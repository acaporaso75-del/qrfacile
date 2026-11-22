"""Customer area of QRFacile Link (/app/link): create, edit, publish, download.

A Link QR is a qr_items row with module='link' (qr_type stays 'external' for
compatibility with the beta rows). Its payload keeps the content of every
type the customer filled in, so switching type never loses work:
    {"type": "pdf", "content": {"link": {...}, "pdf": {...}}, "url": "..."}
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import csrf_input, require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.legal_core import LINK_TERMS_SUMMARY, has_link_acceptance, record_link_acceptance
from qrfacile_app.modules import switches
from qrfacile_app.modules.content_types import CONTENT_TYPES, ContentError
from qrfacile_app.modules.public import _content
from qrfacile_app.modules.stats import STATS_LEVELS, summary
from qrfacile_app.ui_shell import esc, page, pill
from qrfacile_app.services.storage import get_uploads_dir
from qrfacile_app.util import new_slug

router = APIRouter()
ROLES = ("business", "winery", "studio", "admin")
FREE_LINK_QR = 3
MAX_NAME = 80
TYPE_HELP = {
    "link": "Il QR apre un indirizzo web: sito, prenotazioni, Instagram.",
    "pdf": "Il QR apre un documento: listino, menu, catalogo, istruzioni.",
    "minipage": "Il QR apre una piccola pagina con logo, testo e pulsanti (chiama, WhatsApp, mappa...).",
}
STATS_HELP = {
    "none": ("Nessuna statistica", "Non contiamo le scansioni."),
    "counts": ("Solo il numero di scansioni", "Quante volte al giorno viene aperto il QR."),
    "detailed": ("Statistiche dettagliate", "Anche ora del giorno, tipo di dispositivo e lingua. Mai dati personali."),
}


def _user(request: Request) -> dict:
    user = require_any_role(request, ROLES)
    if not switches.migration_applied():
        raise HTTPException(404, "Not found")
    switches.require_module("link", user)
    return user


def _accepted(cur, user: dict) -> bool:
    if (user.get("role") or "").lower() == "admin":
        return True
    return has_link_acceptance(cur, int(user["id"]))


def _acceptance_form(request: Request) -> str:
    return f"""
    <section class="card">
      <h2 class="h2">Prima di iniziare</h2>
      <p class="p">{esc(LINK_TERMS_SUMMARY)}</p>
      <p class="p">Testo completo: <a href="/terms" target="_blank" rel="noopener">Termini di servizio</a> e
      <a href="/privacy" target="_blank" rel="noopener">informativa privacy</a>.</p>
      <form method="post" action="/app/link/accept" style="display:grid;gap:12px">
        {csrf_input(request)}
        <div style="display:flex;gap:10px;align-items:flex-start">
          <input type="checkbox" id="link-accept" name="accept" value="yes" required style="margin-top:4px">
          <label for="link-accept">Accetto le condizioni d'uso di QRFacile Link e ho letto come vengono trattate le statistiche.</label>
        </div>
        <button class="btn btn-primary" type="submit">Accetto e continuo</button>
      </form>
    </section>
    """


def _now() -> int:
    return int(time.time())


def _go(path: str, *, msg: str = "", err: str = "") -> RedirectResponse:
    query = f"?msg={quote(msg)}" if msg else (f"?err={quote(err)}" if err else "")
    return RedirectResponse(f"{path}{query}", status_code=303)


def _owned(cur, qr_id: int, user: dict) -> dict:
    cur.execute(
        """
        SELECT id, owner_user_id, slug, title, status, payload, public_path,
               to_jsonb(q)->>'stats_level' AS stats_level
        FROM qr_items q
        WHERE id=%s AND (to_jsonb(q)->>'module'='link' OR qr_type='external')
        LIMIT 1
        """,
        (int(qr_id),),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "QR non trovato")
    if int(row["owner_user_id"] or 0) != int(user["id"]) and (user.get("role") or "").lower() != "admin":
        raise HTTPException(403, "Forbidden")
    row["payload"] = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    return row


def _public_url(request: Request, slug: str) -> str:
    base = str(getattr(request.app.state, "app_base_url", "") or "").rstrip("/")
    if not base:
        base = f"{request.url.scheme}://{request.headers.get('host', 'localhost:8000')}"
    return f"{base}/d/{slug}"


def _render(request: Request, user: dict, title: str, body: str, msg: str = "", err: str = "") -> HTMLResponse:
    return HTMLResponse(page(
        title=f"QRFACILE · {title}",
        subtitle="QRFacile Link",
        body_html=body,
        msg=msg,
        err=err,
        role=user.get("role", ""),
        user_email=user.get("email", ""),
        credits=None,
    ))


def _state_pill(status: str) -> str:
    status = (status or "").lower()
    if status == "sospesa":
        return pill("Sospeso", "warn")
    return pill("Attivo", "green") if status == "attiva" else pill("Bozza", "muted")


@router.get("/app/link", response_class=HTMLResponse)
def link_list(request: Request, msg: str = "", err: str = ""):
    user = _user(request)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if not _accepted(cur, user):
                return _render(request, user, "I miei QR", _acceptance_form(request), msg, err)
            cur.execute(
                """
                SELECT q.id, q.title, q.status, q.payload, to_jsonb(q)->>'stats_level' AS stats_level,
                       (SELECT COALESCE(SUM(s.scans),0) FROM qr_scan_daily s
                         WHERE s.qr_item_id=q.id AND s.day >= current_date - 29) AS scans
                FROM qr_items q
                WHERE q.owner_user_id=%s AND (to_jsonb(q)->>'module'='link' OR q.qr_type='external')
                ORDER BY q.id DESC
                """,
                (int(user["id"]),),
            )
            rows = cur.fetchall() or []
    if not rows:
        body = """
        <section class="card">
          <h2 class="h2">Il tuo primo QR in 3 passi</h2>
          <ol class="p" style="line-height:1.8;list-style:none;padding-left:0">
            <li>1. Dai un nome al QR e scegli cosa deve aprire: un link, un PDF o una mini-pagina.</li>
            <li>2. Inserisci il contenuto e premi Pubblica.</li>
            <li>3. Scarica il QR e stampalo. Potrai cambiare il contenuto quando vuoi: il QR stampato resta lo stesso.</li>
          </ol>
          <p><a class="btn btn-primary" href="/app/link/new">Crea un QR</a></p>
          <p class="muted">I primi 3 QR sono gratuiti.</p>
        </section>
        """
        return _render(request, user, "I miei QR", body, msg, err)
    items = []
    for row in rows:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        kind = CONTENT_TYPES.get(payload.get("type") or "link")
        scans = (
            f"<span class='muted'>{int(row.get('scans') or 0)} scansioni negli ultimi 30 giorni</span>"
            if (row.get("stats_level") or "none") != "none" else ""
        )
        items.append(
            f"""
            <li class="card" style="margin-top:10px;list-style:none">
              <div class="row" style="justify-content:space-between;gap:8px;flex-wrap:wrap">
                <a href="/app/link/{int(row['id'])}"><b>{esc(row.get('title') or 'QR senza nome')}</b></a>
                {_state_pill(row.get('status') or '')}
              </div>
              <p class="p" style="margin:6px 0 0">{esc(kind.label if kind else 'Link')} {scans}</p>
            </li>
            """
        )
    body = f"""
    <p><a class="btn btn-primary" href="/app/link/new">Crea un QR</a></p>
    <ul style="padding:0;margin:0">{''.join(items)}</ul>
    """
    return _render(request, user, "I miei QR", body, msg, err)


@router.get("/app/link/new", response_class=HTMLResponse)
def link_new_get(request: Request, err: str = ""):
    user = _user(request)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if not _accepted(cur, user):
                return RedirectResponse("/app/link", status_code=303)
    options = "".join(
        f"""
        <div style="display:flex;gap:10px;align-items:flex-start;margin-top:8px">
          <input type="radio" id="kind-{key}" name="kind" value="{key}"{' checked' if key == 'link' else ''}>
          <label for="kind-{key}"><b>{esc(ctype.label)}</b> · {esc(TYPE_HELP.get(key, ''))}</label>
        </div>
        """
        for key, ctype in CONTENT_TYPES.items()
    )
    body = f"""
    <section class="card">
      <form method="post" action="/app/link/new" style="display:grid;gap:14px">
        {csrf_input(request)}
        <div><label for="link-name">Nome del QR (lo vedi solo tu)</label>
          <input id="link-name" class="input" name="name" maxlength="{MAX_NAME}" required placeholder="Es. Menu del bar"></div>
        <fieldset style="border:1px solid rgba(15,23,42,.14);border-radius:14px;padding:14px">
          <legend style="font-weight:800;padding:0 6px">Cosa deve aprire il QR?</legend>
          {options}
          <p class="muted" style="margin-top:8px">Puoi cambiarlo anche dopo la stampa.</p>
        </fieldset>
        <button class="btn btn-primary" type="submit">Crea il QR</button>
      </form>
    </section>
    """
    return _render(request, user, "Nuovo QR", body, err=err)


@router.post("/app/link/new")
def link_new_post(request: Request, name: str = Form(""), kind: str = Form("link")):
    require_csrf_or_same_origin(request)
    user = _user(request)
    uid = int(user["id"])
    name = " ".join((name or "").split())[:MAX_NAME] or "QR senza nome"
    if kind not in CONTENT_TYPES:
        return _go("/app/link/new", err="Tipo di contenuto non disponibile")
    ts = _now()
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if not _accepted(cur, user):
                return RedirectResponse("/app/link", status_code=303)
            # Serialise concurrent creations of the same user (free quota).
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('link-create'), %s)", (uid,))
            cur.execute(
                """SELECT COUNT(*) AS c FROM qr_items q
                   WHERE owner_user_id=%s AND (to_jsonb(q)->>'module'='link' OR qr_type='external')""",
                (uid,),
            )
            paid = int((cur.fetchone() or {}).get("c") or 0) >= FREE_LINK_QR
            if paid:
                cur.execute(
                    """SELECT COALESCE(SUM(delta),0) AS balance FROM available_credit_ledger
                       WHERE user_id=%s AND credit_type='generic'""",
                    (uid,),
                )
                if int((cur.fetchone() or {}).get("balance") or 0) < 1:
                    conn.rollback()
                    return _go("/app/billing", err="Hai usato i 3 QR gratuiti: acquista un pacchetto QR Link per continuare.")
            slug = new_slug()
            cur.execute(
                """
                INSERT INTO qr_items (owner_user_id, winery_id, qr_type, module, stats_level, status, slug, title,
                                      has_back, public_path, payload, created_at, updated_at)
                VALUES (%s, NULL, 'external', 'link', 'none', 'bozza', %s, %s, 0, %s, %s::jsonb, %s, %s)
                RETURNING id
                """,
                (uid, slug, name, f"/d/{slug}", json.dumps({"type": kind, "content": {}}), ts, ts),
            )
            qr_id = int(cur.fetchone()["id"])
            if paid:
                cur.execute(
                    """INSERT INTO credit_ledger (user_id, credit_type, delta, reason, ref_table, ref_id, created_at)
                       VALUES (%s, 'generic', -1, 'simple_qr_extra', 'qr_items', %s, %s)""",
                    (uid, qr_id, ts),
                )
        conn.commit()
    return RedirectResponse(f"/app/link/{qr_id}", status_code=303)


def _stats_html(cur, row: dict) -> str:
    level = row.get("stats_level") or "none"
    if level == "none":
        return ""
    data = summary(cur, qr_item_id=int(row["id"]), days=30)
    parts = [f"<p class='p'><b>{data['total']}</b> scansioni negli ultimi 30 giorni.</p>"]
    if data["by_day"]:
        days = "".join(f"<li>{esc(d.strftime('%d/%m'))}: {n}</li>" for d, n in data["by_day"][-7:])
        parts.append(f"<p class='p'>Ultimi giorni:</p><ul>{days}</ul>")
    labels = {"iphone": "iPhone", "android": "Android", "tablet": "Tablet", "computer": "Computer", "other": "Altro"}
    if data["by_device"]:
        parts.append("<p class='p'>Dispositivi: " + ", ".join(
            f"{esc(labels.get(k, k))} {n}" for k, n in data["by_device"]) + "</p>")
    if data["by_lang"]:
        parts.append("<p class='p'>Lingue: " + ", ".join(f"{esc(k)} {n}" for k, n in data["by_lang"]) + "</p>")
    return "<section class='card' style='margin-top:14px'><h2 class='h2'>Statistiche</h2>" + "".join(parts) + "</section>"


@router.get("/app/link/{qr_id}", response_class=HTMLResponse)
def link_detail(request: Request, qr_id: int, msg: str = "", err: str = ""):
    user = _user(request)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            row = _owned(cur, qr_id, user)
            stats_html = _stats_html(cur, row)
    payload = row["payload"]
    current = payload.get("type") or "link"
    contents = payload.get("content") or {}
    if current == "link" and not contents.get("link") and payload.get("url"):
        contents = {**contents, "link": {"url": payload["url"]}}
    token = csrf_input(request)
    qid = int(row["id"])
    editors = "".join(
        f"""
        <details class="card" style="margin-top:10px"{' open' if key == current else ''}>
          <summary style="cursor:pointer;font-weight:800">{esc(ctype.label)}{' · in uso' if key == current else ''}</summary>
          <p class="muted">{esc(TYPE_HELP.get(key, ''))}</p>
          <form method="post" action="/app/link/{qid}/content" enctype="multipart/form-data" style="display:grid;gap:10px">
            {token}
            <input type="hidden" name="type" value="{key}">
            {ctype.editor_html(contents.get(key))}
            <button class="btn btn-primary" type="submit">Usa {esc(ctype.label)} e salva</button>
          </form>
        </details>
        """
        for key, ctype in CONTENT_TYPES.items()
    )
    level = row.get("stats_level") or "none"
    radios = "".join(
        f"""
        <div style="display:flex;gap:10px;align-items:flex-start;margin-top:6px">
          <input type="radio" id="stats-{key}" name="level" value="{key}"{' checked' if key == level else ''}>
          <label for="stats-{key}"><b>{esc(STATS_HELP[key][0])}</b> · {esc(STATS_HELP[key][1])}</label>
        </div>
        """
        for key in STATS_LEVELS
    )
    active = (row.get("status") or "").lower() == "attiva"
    public = _public_url(request, str(row["slug"]))
    status_form = f"""
    <form method="post" action="/app/link/{qid}/status" style="display:inline">
      {token}
      <input type="hidden" name="status" value="{'bozza' if active else 'attiva'}">
      <button class="btn{'' if active else ' btn-primary'}" type="submit">{'Metti in bozza' if active else 'Pubblica'}</button>
    </form>
    """
    try_link = f'<a class="btn" href="/d/{esc(row["slug"])}" target="_blank" rel="noopener">Prova il QR</a>' if active else ""
    body = f"""
    <section class="card">
      <div class="row" style="justify-content:space-between;gap:8px;flex-wrap:wrap">
        <h2 class="h2" style="margin:0">{esc(row.get('title') or 'QR senza nome')}</h2>
        {_state_pill(row.get('status') or '')}
      </div>
      <div style="display:flex;gap:18px;flex-wrap:wrap;margin-top:12px;align-items:center">
        <img src="/app/link/{qid}/qr.png" alt="QR code di {esc(row.get('title') or '')}" width="160" height="160"
             style="border:1px solid rgba(15,23,42,.12);border-radius:12px;background:#fff">
        <div>
          <p class="p">Indirizzo del QR: <code>{esc(public)}</code></p>
          <p class="p">Contenuto in uso: <b>{esc(CONTENT_TYPES[current].label if current in CONTENT_TYPES else current)}</b></p>
          <div class="row" style="gap:8px;flex-wrap:wrap">
            {status_form}{try_link}
            <a class="btn" href="/app/link/{qid}/qr.png" download>Scarica PNG</a>
            <a class="btn" href="/app/link/{qid}/qr.svg" download>Scarica SVG</a>
            <a class="btn" href="/app/link/{qid}/qr.pdf" download>Scarica PDF</a>
          </div>
        </div>
      </div>
    </section>
    <section style="margin-top:14px">
      <h2 class="h2">Cosa apre il QR</h2>
      {editors}
    </section>
    <section class="card" style="margin-top:14px">
      <form method="post" action="/app/link/{qid}/stats">
        {token}
        <fieldset style="border:0;padding:0;margin:0">
          <legend class="h2" style="font-size:20px">Statistiche</legend>
          {radios}
        </fieldset>
        <button class="btn" type="submit" style="margin-top:10px">Salva scelta statistiche</button>
      </form>
    </section>
    {stats_html}
    <p style="margin-top:14px"><a href="/app/link">Torna ai miei QR</a></p>
    """
    return _render(request, user, "QR Link", body, msg, err)


@router.post("/app/link/{qr_id}/content")
async def link_content_post(request: Request, qr_id: int):
    require_csrf_or_same_origin(request)
    user = _user(request)
    form = await request.form()
    fields = {key: value for key, value in form.items() if isinstance(value, str)}
    files = {key: value for key, value in form.items() if not isinstance(value, str)}
    kind = fields.get("type") or ""
    if kind not in CONTENT_TYPES:
        return _go(f"/app/link/{int(qr_id)}", err="Tipo di contenuto non disponibile")
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if not _accepted(cur, user):
                return RedirectResponse("/app/link", status_code=303)
            row = _owned(cur, qr_id, user)
            payload = dict(row["payload"])
            contents = dict(payload.get("content") or {})
            if not contents.get("link") and payload.get("url"):
                contents["link"] = {"url": payload["url"]}
            try:
                parsed = CONTENT_TYPES[kind].parse(fields, files, contents.get(kind), qr_item_id=int(row["id"]))
            except ContentError as exc:
                conn.rollback()
                return _go(f"/app/link/{int(qr_id)}", err=str(exc))
            contents[kind] = parsed
            payload["type"] = kind
            payload["content"] = contents
            if contents.get("link"):
                payload["url"] = contents["link"]["url"]
            replaced = _stored_files(row["payload"]) - _stored_files(payload)
            cur.execute(
                "UPDATE qr_items SET payload=%s::jsonb, module='link', updated_at=%s WHERE id=%s",
                (json.dumps(payload), _now(), int(row["id"])),
            )
        conn.commit()
    _delete_files(replaced, int(row["id"]))
    return _go(f"/app/link/{int(qr_id)}", msg="Contenuto salvato")


def _stored_files(payload: dict) -> set[str]:
    contents = (payload or {}).get("content") or {}
    files = {
        str((contents.get("pdf") or {}).get("file") or ""),
        str((contents.get("minipage") or {}).get("logo") or ""),
    }
    return {f for f in files if f}


def _delete_files(paths: set[str], qr_item_id: int) -> None:
    """Remove files no longer referenced; only inside this QR's own folder."""
    base = (Path(get_uploads_dir()) / "modules" / "link" / str(int(qr_item_id))).resolve()
    for relative in paths:
        target = (Path(get_uploads_dir()) / relative).resolve()
        if target.parent == base and target.is_file():
            try:
                target.unlink()
            except OSError:
                pass


@router.post("/app/link/{qr_id}/stats")
def link_stats_post(request: Request, qr_id: int, level: str = Form("")):
    require_csrf_or_same_origin(request)
    user = _user(request)
    if level not in STATS_LEVELS:
        raise HTTPException(422, "Scelta statistiche non valida")
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            row = _owned(cur, qr_id, user)
            cur.execute("UPDATE qr_items SET stats_level=%s, updated_at=%s WHERE id=%s", (level, _now(), int(row["id"])))
        conn.commit()
    return _go(f"/app/link/{int(qr_id)}", msg="Scelta statistiche salvata")


@router.post("/app/link/{qr_id}/status")
def link_status_post(request: Request, qr_id: int, status: str = Form("")):
    require_csrf_or_same_origin(request)
    user = _user(request)
    if status not in ("attiva", "bozza"):
        raise HTTPException(422, "Stato non valido")
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            row = _owned(cur, qr_id, user)
            if (row.get("status") or "").lower() == "sospesa" and (user.get("role") or "").lower() != "admin":
                conn.rollback()
                return _go(f"/app/link/{int(qr_id)}", err="QR sospeso dopo una segnalazione: scrivi a info@qrfacile.it.")
            if status == "attiva" and _content(row["payload"]) is None:
                conn.rollback()
                return _go(f"/app/link/{int(qr_id)}", err="Completa il contenuto prima di pubblicare.")
            cur.execute("UPDATE qr_items SET status=%s, updated_at=%s WHERE id=%s", (status, _now(), int(row["id"])))
        conn.commit()
    return _go(f"/app/link/{int(qr_id)}", msg="QR pubblicato" if status == "attiva" else "QR messo in bozza")


@router.get("/app/link/{qr_id}/qr.{fmt}")
def link_qr_file(request: Request, qr_id: int, fmt: str):
    from qrfacile_app import export_qr_ui

    user = _user(request)
    if fmt not in ("png", "svg", "pdf"):
        raise HTTPException(404, "Formato non disponibile")
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            row = _owned(cur, qr_id, user)
    url = _public_url(request, str(row["slug"]))
    if fmt == "png":
        data, media = export_qr_ui._qr_png(url, 30, 600), "image/png"
    elif fmt == "svg":
        data, media = export_qr_ui._qr_svg(url), "image/svg+xml"
    else:
        data, media = export_qr_ui._qr_pdf_a4(url, 30, 600), "application/pdf"
    return Response(data, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="qrfacile-link-{row["slug"]}.{fmt}"',
        "Cache-Control": "no-store",
    })


@router.post("/app/link/accept")
def link_accept_post(request: Request, accept: str = Form("")):
    require_csrf_or_same_origin(request)
    user = _user(request)
    if accept != "yes":
        return _go("/app/link", err="Per usare QRFacile Link devi accettare le condizioni.")
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            record_link_acceptance(cur, user_id=int(user["id"]), request=request)
        conn.commit()
    return _go("/app/link", msg="Condizioni accettate")
