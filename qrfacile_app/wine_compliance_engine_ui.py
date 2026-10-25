from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.services.collaboration_access import require_wine_access
from qrfacile_app.services.recycling_catalog import normalize_recycling_items
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
            recycle = normalize_recycling_items(
                {row["component"]: dict(row) for row in cur.fetchall()}
            )

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


def _evidence_html(value) -> str:
    if not value:
        return "—"
    if isinstance(value, dict):
        return "<dl class='ceEvidence'>" + "".join(
            f"<dt>{esc(str(key).replace('_', ' ').capitalize())}</dt>"
            f"<dd>{esc(json.dumps(item, ensure_ascii=False, default=str) if isinstance(item, (dict, list)) else str(item))}</dd>"
            for key, item in value.items()
        ) + "</dl>"
    return esc(str(value))


def _report_html(report: dict, *, verified_at: datetime | None = None) -> str:
    verification_time = (verified_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    verification_label = verification_time.strftime("%d/%m/%Y %H:%M UTC")
    counts = report.get("counts") or {}
    score = esc(str(report.get("score") if report.get("score") is not None else "—"))
    warning_count = esc(str(counts.get("WARNING") or 0))
    rows = []
    for item in report["results"]:
        status = str(item.get("status") or "")
        badge_class = {"PASS": "ok", "WARNING": "warn", "ERROR": "err"}.get(status, "")
        remediation = item.get("remediation") or "—"
        evidence_html = _evidence_html(item.get("evidence"))
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
              <td><b>{esc(str(item.get('title') or ''))}</b><div class='ceRule'>{esc(str(item.get('rule_id') or ''))} · {esc(str(item.get('version') or ''))}</div></td>
              <td>{esc(str(item.get('explanation') or ''))}</td>
              <td>{evidence_html}</td>
              <td>{esc(remediation)}</td>
              <td>{source_html}</td>
            </tr>
            """
        )

    publishable = bool(report.get("publishable"))
    blocking_count = int(report.get("blocking_error_count") or sum(
        1 for item in report.get("results", [])
        if item.get("status") == "ERROR" and item.get("blocking")
    ))
    general_status = "Conforme ai controlli automatici" if publishable else "Correzioni obbligatorie"
    publish_text = "Sì" if publishable else "No"
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
      .ceEvidence{{margin:0;display:grid;grid-template-columns:minmax(110px,auto) 1fr;gap:4px 8px}}
      .ceEvidence dt{{font-weight:700}}.ceEvidence dd{{margin:0;overflow-wrap:anywhere}}
      @media(max-width:900px){{.ceGrid{{grid-template-columns:repeat(2,1fr)}}.ceTable{{display:block;overflow:auto}}}}
    </style>
    <div class='card'>
      <div class='h1'>Report di conformità</div>
      <div class='p'>Verifica automatica leggibile e motivata. Il risultato supporta la revisione umana e non costituisce certificazione automatica.</div>
      <div class='ceGrid'>
        <div class='ceMetric'><span>Score</span><b>{score}/100</b></div>
        <div class='ceMetric'><span>Pubblicabile</span><b>{publish_text}</b></div>
        <div class='ceMetric'><span>Errori bloccanti</span><b>{blocking_count}</b></div>
        <div class='ceMetric'><span>Avvisi</span><b>{warning_count}</b></div>
      </div>
      <div class='p'><b>Stato generale: {esc(general_status)}</b></div>
      <div class='p'>Versione motore {esc(str(report.get('engine_version') or ''))} · catalogo regole {esc(str(report.get('catalog_version') or ''))} · base conoscenza {esc(str(report.get('knowledge_version') or ''))} · verifica del {esc(verification_label)}.</div>
    </div>
    <div class='card' style='margin-top:14px'>
      <div class='h2'>Esiti motivati</div>
      <table class='ceTable'>
        <thead><tr><th>Esito</th><th>Regola</th><th>Motivo</th><th>Evidenza</th><th>Azione correttiva</th><th>Fonte e contesto</th></tr></thead>
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
    return HTMLResponse(page(
        title="Report di conformità",
        subtitle="Esito motivato della verifica corrente",
        body_html=body,
        user_email=str(user.get("email") or ""),
        role=str(user.get("role") or ""),
        credits=user.get("credits") if isinstance(user.get("credits"), dict) else None,
    ))


@router.get("/api/wines/{wine_id}/compliance-report", response_class=JSONResponse)
def compliance_report_api(request: Request, wine_id: int):
    user = require_any_role(request, ("admin", "studio", "winery"))
    payload = _load_payload(wine_id, user)
    return JSONResponse(run_explainable_wine_compliance(payload))
