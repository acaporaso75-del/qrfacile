from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.wine_compliance_explainability import run_explainable_wine_compliance
from qrfacile_app.ui_shell import esc
from qrfacile_app.wine_compliance_engine_ui import _load_payload
from qrfacile_app.wine_hub_ui import wine_hub

router = APIRouter(tags=["wine-compliance-center"])


def _compact_compliance_html(report: dict, wine_id: int) -> str:
    publishable = bool(report.get("publishable"))
    counts = report.get("counts") or {}
    score = int(report.get("score") or 0)
    errors = int(counts.get("ERROR") or 0)
    warnings = int(counts.get("WARNING") or 0)
    passes = int(counts.get("PASS") or 0)

    state_class = "ok" if publishable else "blocked"
    state_title = "Pubblicazione consentita" if publishable else "Pubblicazione bloccata"
    state_text = (
        "Nessun errore bloccante rilevato dal motore deterministico."
        if publishable
        else "Correggi gli errori indicati prima di pubblicare."
    )

    priority = [
        item for item in report.get("results", [])
        if item.get("status") in {"ERROR", "WARNING"}
    ][:3]

    if priority:
        issues = "".join(
            f"""
            <li>
              <span class='wineComplianceIssueStatus {esc(item.get('status', '').lower())}'>{esc(item.get('status', ''))}</span>
              <div>
                <b>{esc(item.get('title') or item.get('rule_id') or 'Controllo')}</b>
                <span>{esc(item.get('explanation') or '')}</span>
              </div>
            </li>
            """
            for item in priority
        )
    else:
        issues = "<li><div><b>Nessuna criticità prioritaria</b><span>I controlli correnti non richiedono correzioni immediate.</span></div></li>"

    return f"""
    <section class='card wineComplianceCenter {state_class}' aria-labelledby='wine-compliance-title'>
      <div class='wineComplianceHead'>
        <div>
          <div class='wineHubSmallLabel'>Compliance Center</div>
          <div class='h2' id='wine-compliance-title'>Stato normativo del lotto</div>
          <div class='p'>Controlli deterministici, motivati e soggetti a revisione umana.</div>
        </div>
        <div class='wineComplianceActions'>
          <a class='btn' href='/app/wine/{int(wine_id)}/compliance-replays'>Storico replay</a>
          <a class='btn' href='/app/wine/{int(wine_id)}/compliance-report'>Apri report completo</a>
        </div>
      </div>

      <div class='wineComplianceGrid'>
        <div class='wineComplianceScore'>
          <span>Compliance score</span>
          <b>{score}<small>/100</small></b>
          <div class='wineComplianceBar' role='progressbar' aria-valuemin='0' aria-valuemax='100' aria-valuenow='{score}'>
            <i style='width:{max(0, min(score, 100))}%'></i>
          </div>
        </div>
        <div class='wineComplianceDecision'>
          <span class='wineComplianceDecisionBadge'>{esc(state_title)}</span>
          <b>{errors} errori · {warnings} avvisi · {passes} controlli superati</b>
          <p>{esc(state_text)}</p>
          <small>Engine {esc(str(report.get('engine_version') or ''))} · catalogo {esc(str(report.get('catalog_version') or ''))} · knowledge {esc(str(report.get('knowledge_version') or ''))}</small>
        </div>
      </div>

      <ul class='wineComplianceIssues'>{issues}</ul>

      <style>
        .wineComplianceCenter{{margin-top:18px;border-left:6px solid #0f766e}}
        .wineComplianceCenter.blocked{{border-left-color:#b91c1c}}
        .wineComplianceHead{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;flex-wrap:wrap}}
        .wineComplianceActions{{display:flex;gap:8px;flex-wrap:wrap}}
        .wineComplianceGrid{{display:grid;grid-template-columns:minmax(220px,.75fr) minmax(280px,1.25fr);gap:16px;margin-top:18px}}
        .wineComplianceScore,.wineComplianceDecision{{border:1px solid rgba(2,8,23,.08);border-radius:20px;padding:18px;background:rgba(255,255,255,.72)}}
        .wineComplianceScore>span{{display:block;color:#64748b;font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.06em}}
        .wineComplianceScore>b{{display:block;font-size:42px;line-height:1;margin:12px 0}}
        .wineComplianceScore small{{font-size:16px;color:#64748b}}
        .wineComplianceBar{{height:10px;border-radius:999px;background:#e2e8f0;overflow:hidden}}
        .wineComplianceBar i{{display:block;height:100%;border-radius:999px;background:#0f766e}}
        .blocked .wineComplianceBar i{{background:#b91c1c}}
        .wineComplianceDecisionBadge{{display:inline-flex;padding:7px 11px;border-radius:999px;background:#dcfce7;color:#166534;font-size:12px;font-weight:900;text-transform:uppercase}}
        .blocked .wineComplianceDecisionBadge{{background:#fee2e2;color:#991b1b}}
        .wineComplianceDecision b{{display:block;margin-top:14px}}
        .wineComplianceDecision p{{margin:7px 0;color:#475569}}
        .wineComplianceDecision small{{color:#64748b}}
        .wineComplianceIssues{{list-style:none;padding:0;margin:16px 0 0;display:grid;gap:10px}}
        .wineComplianceIssues li{{display:flex;gap:12px;align-items:flex-start;border-top:1px solid rgba(2,8,23,.07);padding-top:12px}}
        .wineComplianceIssues li div{{display:grid;gap:3px}}
        .wineComplianceIssues li span:not(.wineComplianceIssueStatus){{color:#64748b;font-size:13px}}
        .wineComplianceIssueStatus{{display:inline-flex;min-width:72px;justify-content:center;padding:5px 8px;border-radius:999px;font-size:11px;font-weight:900}}
        .wineComplianceIssueStatus.error{{background:#fee2e2;color:#991b1b}}
        .wineComplianceIssueStatus.warning{{background:#fef3c7;color:#92400e}}
        @media(max-width:760px){{.wineComplianceGrid{{grid-template-columns:1fr}}}}
      </style>
    </section>
    """


@router.get("/app/wine/{wine_id}", response_class=HTMLResponse)
def wine_hub_with_compliance(request: Request, wine_id: int, tab: str | None = None):
    user = require_any_role(request, ("winery", "studio", "admin"))
    base_response = wine_hub(request, wine_id, tab)
    if isinstance(base_response, RedirectResponse):
        return base_response

    payload = _load_payload(int(wine_id), user)
    report = run_explainable_wine_compliance(payload)
    compliance_html = _compact_compliance_html(report, int(wine_id))

    html = base_response.body.decode(base_response.charset or "utf-8")
    marker = '<div class="card wineHubActionBar">'
    if marker in html:
        html = html.replace(marker, compliance_html + marker, 1)
    else:
        html = html.replace("</section>", compliance_html + "</section>", 1)

    return HTMLResponse(html, status_code=base_response.status_code)
