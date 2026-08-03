from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import csrf_input
from qrfacile_app.db import pg
from qrfacile_app.guided_flow import render_guided_stepper
from qrfacile_app.services.storage import asset_url, verify_saved_asset
from qrfacile_app.services.wine_compliance_explainability import run_explainable_wine_compliance
from qrfacile_app.ui_shell import esc, page
from qrfacile_app.wine_compliance_engine_ui import _load_payload

router = APIRouter(tags=["wine-guided-flow"])


def _context(wine_id: int, user: dict) -> dict:
    payload = _load_payload(wine_id, user)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT qi.slug, qi.status FROM qr_wines qw JOIN qr_items qi ON qi.id=qw.qr_item_id
                   WHERE qw.id=%s LIMIT 1""", (int(wine_id),),
            )
            qr = cur.fetchone() or {}
            cur.execute(
                """SELECT kind, img_original, img_optimized, img_thumb, updated_at
                   FROM wine_assets WHERE wine_id=%s""", (int(wine_id),),
            )
            assets = {row["kind"]: dict(row) for row in cur.fetchall()}
    return {"payload": payload, "report": run_explainable_wine_compliance(payload), "qr": dict(qr), "assets": assets}


def _image_preview(asset: dict, label: str) -> str:
    thumb = asset.get("img_thumb") or ""
    try:
        verify_saved_asset({"thumb": thumb})
        return f'<figure><img src="{esc(asset_url(thumb, asset.get("updated_at")))}" alt="{esc(label)}" style="width:100%;max-height:280px;object-fit:contain"><figcaption>{esc(label)} disponibile</figcaption></figure>'
    except (OSError, ValueError):
        return f'<div class="note"><b>{esc(label)} non disponibile.</b> Carica o sostituisci il file nello step Immagini.</div>'


def _list(items: list[str], empty: str) -> str:
    return "<ul>" + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>" if items else f"<p>{esc(empty)}</p>"


@router.get("/app/wine/{wine_id}/review", response_class=HTMLResponse)
def review(request: Request, wine_id: int, msg: str = ""):
    user = require_any_role(request, ("admin", "studio", "winery"))
    ctx = _context(wine_id, user)
    payload, report, qr, assets = ctx["payload"], ctx["report"], ctx["qr"], ctx["assets"]
    blocking = [item for item in report["results"] if item["status"] == "ERROR" and item.get("blocking")]
    warnings = [item for item in report["results"] if item["status"] == "WARNING"]
    published = str(qr.get("status") or "").lower() == "attiva"
    slug = str(qr.get("slug") or "")
    role = str(user.get("role") or "").lower()
    if blocking:
        primary = f'<a class="btn btn-primary" href="/app/wine/{wine_id}/compliance">Correggi dati</a>'
    elif not published and role in ("winery", "admin"):
        primary = f'<form method="post" action="/app/wine/{wine_id}/publish">{csrf_input(request)}<button class="btn btn-primary" type="submit">Pubblica etichetta</button></form>'
    elif published:
        primary = f'<a class="btn btn-primary" href="/app/wine/{wine_id}/complete">Continua</a>'
    else:
        primary = '<div class="note">Solo la cantina proprietaria può pubblicare.</div>'
    result_rows = "".join(
        f'<li><a href="/app/wine/{wine_id}/compliance#{"nutrizione" if str(item.get("field") or "").startswith("nutrition") else "riciclabilita" if item.get("field")=="recycle" else "ingredienti"}"><b>{esc(item["title"])}</b> — {esc(item.get("remediation") or item["explanation"])}</a></li>'
        for item in blocking + warnings
    ) or "<li>Nessun errore bloccante o avviso.</li>"
    recycle = payload.get("recycle") or {}
    recycle_rows = "".join(f'<li><b>{esc(key.capitalize())}</b>: {esc(row.get("product") or "—")} · {esc(row.get("code") or "—")}</li>' for key, row in recycle.items()) or "<li>Nessun componente</li>"
    nut = payload.get("nutrition") or {}
    body = f"""
    <section style="max-width:1180px;margin:auto"><div class="h1">Controllo finale dell’etichetta</div>
      <p>Controlla tutti i dati in un’unica pagina. La preview è disponibile anche prima della pubblicazione.</p>
      {render_guided_stepper(wine_id, "review", {"wine","images","ingredients","nutrition","recycling"})}
      {f'<div class="note note-ok">{esc(msg)}</div>' if msg else ''}
      <div class="card"><div class="h2">Compliance Score: {report['score']}/100</div><p>{'Pubblicabile' if not blocking else 'Non pubblicabile: correggere gli errori indicati'}</p><ul>{result_rows}</ul></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px">{_image_preview(assets.get('front') or {}, 'Immagine fronte')}{_image_preview(assets.get('back') or {}, 'Immagine retro')}</div>
      <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:16px">
        <div class="card"><div class="h2">Ingredienti</div>{_list(payload.get('ingredients') or [], 'Nessun ingrediente')}</div>
        <div class="card"><div class="h2">Allergeni</div>{_list(payload.get('allergens') or [], 'Nessun allergene dichiarato')}</div>
        <div class="card"><div class="h2">Nutrizione per 100 ml</div><p>{esc(str(nut.get('energy_kj') or '—'))} kJ · {esc(str(nut.get('energy_kcal') or '—'))} kcal</p></div>
        <div class="card"><div class="h2">Riciclabilità</div><ul>{recycle_rows}</ul></div>
      </div>
      <div class="card" style="margin-top:16px"><div class="h2">Anteprima della pagina</div><iframe title="Anteprima etichetta" src="/preview/{esc(slug)}" style="width:100%;height:520px;border:1px solid #ddd;border-radius:14px"></iframe></div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px"><a class="btn" href="/app/wine/{wine_id}/compliance">Indietro</a><a class="btn" href="/app/wine/{wine_id}">Dashboard del lotto</a><a class="btn" target="_blank" href="/preview/{esc(slug)}">Apri anteprima</a>{primary}</div>
    </section>"""
    return HTMLResponse(page(title="QRFACILE · Controllo finale", subtitle="Step 7 di 7", body_html=body, actions_html="", user_email=user.get("email", ""), role=role, credits={}))


@router.get("/app/wine/{wine_id}/complete", response_class=HTMLResponse)
def complete(request: Request, wine_id: int, msg: str = ""):
    user = require_any_role(request, ("admin", "studio", "winery"))
    ctx = _context(wine_id, user)
    qr = ctx["qr"]
    slug = str(qr.get("slug") or "")
    published = str(qr.get("status") or "").lower() == "attiva" and ctx["report"]["publishable"]
    if not published:
        content = f'<div class="note"><b>Etichetta non ancora pubblicata.</b> Completa il controllo finale; la preview rimane disponibile.</div><a class="btn btn-primary" href="/app/wine/{wine_id}/review">Vai al controllo finale</a>'
    else:
        content = f'''<div class="note note-ok"><b>Etichetta pubblicata correttamente</b></div><div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px">
        <a class="btn btn-primary" target="_blank" href="/e/{esc(slug)}">Apri pagina pubblica</a><a class="btn" target="_blank" href="/preview/{esc(slug)}">Apri anteprima</a>
        <a class="btn" target="_blank" href="/app/wine/{wine_id}/export/preview.png">Visualizza QR</a><a class="btn" href="/app/wine/{wine_id}/export/file?preset=label_pro&name=qrfacile">Scarica QR</a>
        <a class="btn" href="/app/wine/{wine_id}/export/file?preset=a4_pdf&name=qrfacile">Esporta PDF</a><a class="btn" href="/app/wine/{wine_id}">Torna alla dashboard</a></div>'''
    body = f'<section style="max-width:1000px;margin:auto"><div class="h1">Pubblicazione etichetta</div>{content}</section>'
    return HTMLResponse(page(title="QRFACILE · Pubblicazione", subtitle="Operazione conclusa", body_html=body, actions_html="", user_email=user.get("email", ""), role=str(user.get("role") or ""), credits={}))
