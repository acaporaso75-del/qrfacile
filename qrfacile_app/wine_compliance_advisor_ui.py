from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.wine_compliance_advisor import build_compliance_advice
from qrfacile_app.services.wine_compliance_explainability import run_explainable_wine_compliance
from qrfacile_app.ui_shell import esc, page
from qrfacile_app.wine_compliance_engine_ui import _load_payload

router = APIRouter(tags=["wine-compliance-advisor"])


def _advisor_html(wine_id: int, advice: dict) -> str:
    rows = []
    for item in advice.get("actions") or []:
        rows.append(f"""
        <tr>
          <td><span class='caPriority {esc(str(item.get('priority') or '').lower())}'>{esc(str(item.get('priority') or ''))}</span></td>
          <td><b>{esc(str(item.get('title') or ''))}</b><div class='caRule'>{esc(str(item.get('rule_id') or ''))}</div></td>
          <td>{esc(str(item.get('reason') or ''))}</td>
          <td>{esc(str(item.get('action') or ''))}</td>
          <td>{esc(str(item.get('field') or '—'))}</td>
          <td>{esc(str(item.get('estimated_minutes') or 0))} min</td>
        </tr>
        """)
    if not rows:
        rows.append("<tr><td colspan='6'>Nessuna azione richiesta. I controlli correnti risultano superati.</td></tr>")

    next_action = advice.get("next_action") or {}
    next_html = (
        f"<b>{esc(str(next_action.get('title') or ''))}</b><span>{esc(str(next_action.get('action') or ''))}</span>"
        if next_action else
        "<b>Nessuna criticità</b><span>Il piano operativo non contiene correzioni pendenti.</span>"
    )

    return f"""
    <style>
      .caGrid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}}
      .caMetric{{padding:16px;border:1px solid var(--border);border-radius:16px;background:var(--card)}}
      .caMetric b{{display:block;font-size:28px;margin-top:5px}}
      .caNext{{display:grid;gap:5px;padding:16px;border-left:5px solid #b91c1c;background:var(--card);border-radius:14px}}
      .caNext span{{color:var(--muted)}}
      .caTable{{width:100%;border-collapse:collapse;background:var(--card)}}
      .caTable th,.caTable td{{border:1px solid var(--border);padding:10px;text-align:left;vertical-align:top}}
      .caPriority{{display:inline-flex;padding:5px 8px;border-radius:999px;font-size:11px;font-weight:900}}
      .caPriority.blocking{{background:#fee2e2;color:#991b1b}}.caPriority.high{{background:#ffedd5;color:#9a3412}}
      .caPriority.medium{{background:#fef3c7;color:#92400e}}.caPriority.info{{background:#e0f2fe;color:#075985}}
      .caRule{{font-size:12px;color:var(--muted);margin-top:3px}}
      @media(max-width:900px){{.caGrid{{grid-template-columns:repeat(2,1fr)}}.caTable{{display:block;overflow:auto}}}}
    </style>
    <div class='card'>
      <div class='h1'>Compliance Advisor</div>
      <div class='p'>Piano deterministico di correzione per il vino {int(wine_id)}. Le priorità derivano dagli esiti del motore e non sostituiscono la revisione professionale.</div>
      <div class='caGrid'>
        <div class='caMetric'><span>Completamento</span><b>{int(advice.get('completion_percent') or 0)}%</b></div>
        <div class='caMetric'><span>Azioni</span><b>{int(advice.get('total_actions') or 0)}</b></div>
        <div class='caMetric'><span>Bloccanti</span><b>{int((advice.get('priority_counts') or {}).get('BLOCKING') or 0)}</b></div>
        <div class='caMetric'><span>Tempo stimato</span><b>{int(advice.get('estimated_total_minutes') or 0)} min</b></div>
      </div>
      <div class='caNext'>{next_html}</div>
      <div class='row' style='margin-top:14px'>
        <a class='btn' href='/app/wine/{int(wine_id)}/compliance-report'>Report completo</a>
        <a class='btn' href='/app/wine/{int(wine_id)}/compliance-replays'>Storico replay</a>
      </div>
    </div>
    <div class='card' style='margin-top:14px'>
      <div class='h2'>Piano operativo ordinato</div>
      <table class='caTable'>
        <thead><tr><th>Priorità</th><th>Controllo</th><th>Motivo</th><th>Azione</th><th>Campo</th><th>Stima</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    """


@router.get("/api/wines/{wine_id}/compliance-advice", response_class=JSONResponse)
def compliance_advice_api(request: Request, wine_id: int):
    user = require_any_role(request, ("admin", "studio", "winery"))
    payload = _load_payload(wine_id, user)
    report = run_explainable_wine_compliance(payload)
    return JSONResponse(build_compliance_advice(report))


@router.get("/app/wine/{wine_id}/compliance-advisor", response_class=HTMLResponse)
def compliance_advisor_page(request: Request, wine_id: int):
    user = require_any_role(request, ("admin", "studio", "winery"))
    payload = _load_payload(wine_id, user)
    advice = build_compliance_advice(run_explainable_wine_compliance(payload))
    return HTMLResponse(page(request, user, "Compliance Advisor", _advisor_html(wine_id, advice)))
