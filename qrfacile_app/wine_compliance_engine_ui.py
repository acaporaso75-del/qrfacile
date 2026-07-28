from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.services.collaboration_access import require_wine_access
from qrfacile_app.services.wine_compliance_explainability import run_explainable_wine_compliance
from qrfacile_app.ui_shell import esc, page

router = APIRouter(tags=["wine-compliance-engine"])


def _load_payload(wine_id: int, user: dict) -> dict:
    require_wine_access(user, wine_id, "view")
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT qw.id AS wine_id, qw.winery_id, qw.wine_name, qw.vintage, qw.lot,
                       w.name AS winery_name, w.owner_user_id
                FROM qr_wines qw
                JOIN wineries w ON w.id = qw.winery_id
                WHERE qw.id=%s
                LIMIT 1
                """,
                (int(wine_id),),
            )
            wine = cur.fetchone()
            if not wine:
                raise HTTPException(404, "Vino non trovato")

            cur.execute(
                """SELECT energy_kj, energy_kcal, fat, saturates, carbs, sugars, protein, salt
                   FROM wine_nutrition WHERE wine_id=%s LIMIT 1""",
                (int(wine_id),),
            )
            nutrition = cur.fetchone() or {}

            cur.execute(
                """SELECT im.name FROM wine_ingredients wi
                   JOIN ingredients_master im ON im.id=wi.ingredient_id
                   WHERE wi.wine_id=%s ORDER BY lower(im.name)""",
                (int(wine_id),),
            )
            ingredients = [row["name"] for row in cur.fetchall() if row.get("name")]

            cur.execute(
                """SELECT COALESCE(am.name, wa.custom_text) AS name
                   FROM wine_allergens wa
                   LEFT JOIN allergens_master am ON am.id=wa.allergen_id
                   WHERE wa.wine_id=%s ORDER BY COALESCE(am.name, wa.custom_text)""",
                (int(wine_id),),
            )
            allergens = [row["name"] for row in cur.fetchall() if row.get("name")]

            cur.execute(
                """SELECT component, product, code, extra_code, note
                   FROM wine_recycle_items WHERE wine_id=%s ORDER BY component""",
                (int(wine_id),),
            )
            recycle = {row["component"]: dict(row) for row in cur.fetchall()}

            cur.execute(
                """SELECT extra_ingredients, story_text, public_theme
                   FROM wine_meta WHERE wine_id=%s LIMIT 1""",
                (int(wine_id),),
            )
            meta = cur.fetchone() or {}

    return {
        "wine": dict(wine),
        "nutrition": dict(nutrition),
        "ingredients": ingredients,
        "allergens": allergens,
        "recycle": recycle,
        "meta": dict(meta),
    }


def _report_html(report: dict) -> str:
    rows = []
    for item in report["results"]:
        status = item["status"]
        badge_class = {"PASS": "ok", "WARNING": "warn", "ERROR": "err"}.get(status, "")
        remediation = item.get("remediation") or "—"
        sources = item.get("knowledge") or []
        source_html = "".join(
            f"<div class='ceSource'><b>{esc(source.get('reference') or source.get('title') or '')}</b>"
            f"<span>{esc(source.get('article') or source.get('summary') or '')}</span></div>"
            for source in sources
        ) or "—"
        rows.append(
            f"""
            <tr>
              <td><span class='ceBadge {badge_class}'>{esc(status)}</span></td>
              <td><b>{esc(item['title'])}</b><div class='ceRule'>{esc(item['rule_id'])} · {esc(item['version'])}</div></td>
              <td>{esc(item['explanation'])}</td>
              <td>{esc(remediation)}</td>
              <td>{source_html}</td>
            </tr>
            """
        )

    publish_text = "Nessun errore bloccante" if report["publishable"] else "Pubblicazione da bloccare"
    return f"""
    <style>
      .ceGrid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:14px 0}}
      .ceMetric{{padding:16px;border:1px solid var(--border);border-radius:14px;background:var(--card)}}
      .ceMetric b{{font-size:26px;display:block}}
      .ceTable{{width:100%;border-collapse:collapse;background:var(--card)}}
      .ceTable th,.ceTable td{{border:1px solid var(--border);padding:12px;text-align:left;vertical-align:top}}
      .ceBadge{{display:inline-block;padding:5px 9px;border-radius:999px;font-weight:800;font-size:12px}}
      .ceBadge.ok{{background:#dcfce7;color:#166534}}.ceBadge.warn{{background:#fef3c7;color:#92400e}}.ceBadge.err{{background:#fee2e2;color:#991b1b}}
      .ceRule{{font-size:12px;color:var(--muted);margin-top:4px}}
      .ceSource{{display:grid;gap:3px;margin-bottom:8px}}.ceSource span{{font-size:12px;color:var(--muted)}}
      @media(max-width:900px){{.ceGrid{{grid-template-columns:repeat(2,1fr)}}.ceTable{{display:block;overflow:auto}}}}
    </style>
    <div class='card'>
      <div class='h1'>Compliance Engine</div>
      <div class='p'>Motore deterministico {esc(report['engine_version'])} · catalogo {esc(report['catalog_version'])} · knowledge {esc(report['knowledge_version'])}. Il risultato supporta la revisione umana e non costituisce certificazione automatica.</div>
      <div class='ceGrid'>
        <div class='ceMetric'><span>Score</span><b>{report['score']}/100</b></div>
        <div class='ceMetric'><span>PASS</span><b>{report['counts']['PASS']}</b></div>
        <div class='ceMetric'><span>WARNING</span><b>{report['counts']['WARNING']}</b></div>
        <div class='ceMetric'><span>ERROR</span><b>{report['counts']['ERROR']}</b></div>
      </div>
      <div class='p'><b>{esc(publish_text)}</b> · Revisione umana obbligatoria.</div>
    </div>
    <div class='card' style='margin-top:14px'>
      <div class='h2'>Esiti motivati</div>
      <table class='ceTable'>
        <thead><tr><th>Esito</th><th>Controllo</th><th>Motivazione</th><th>Azione consigliata</th><th>Fonte e contesto</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


@router.get("/app/wine/{wine_id}/compliance-report", response_class=HTMLResponse)
def compliance_report(request: Request, wine_id: int):
    user = require_any_role(request, ("admin", "studio", "winery"))
    payload = _load_payload(wine_id, user)
    report = run_explainable_wine_compliance(payload)
    body = _report_html(report)
    return HTMLResponse(page(request, user, "Compliance Engine", body))


@router.get("/api/wines/{wine_id}/compliance-report", response_class=JSONResponse)
def compliance_report_api(request: Request, wine_id: int):
    user = require_any_role(request, ("admin", "studio", "winery"))
    payload = _load_payload(wine_id, user)
    return JSONResponse(run_explainable_wine_compliance(payload))