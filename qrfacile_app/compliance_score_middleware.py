from __future__ import annotations

import re
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


WINE_COMPLIANCE_PATH = re.compile(r"^/app/wine/(?P<wine_id>\d+)/compliance/?$")


class ComplianceScoreMiddleware(BaseHTTPMiddleware):
    """Embed the deterministic compliance score in the existing wine page.

    The widget reads the authenticated JSON report from the same origin. It does
    not execute AI and does not alter the existing form or publication workflow.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        match = WINE_COMPLIANCE_PATH.match(request.url.path)
        content_type = response.headers.get("content-type", "").lower()

        if (
            request.method != "GET"
            or not match
            or response.status_code != 200
            or "text/html" not in content_type
        ):
            return response

        body = b"".join([chunk async for chunk in response.body_iterator])
        try:
            html = body.decode("utf-8")
        except UnicodeDecodeError:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        wine_id = int(match.group("wine_id"))
        widget = _score_widget(wine_id)
        marker = "</body>"
        html = html.replace(marker, f"{widget}{marker}", 1) if marker in html else html + widget

        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            content=html,
            status_code=response.status_code,
            headers=headers,
            media_type="text/html",
        )


def _score_widget(wine_id: int) -> str:
    return f"""
<style>
  .qrfScoreWidget{{margin-top:14px;padding:16px;border:1px solid rgba(2,8,23,.08);border-radius:20px;background:rgba(255,255,255,.88);box-shadow:0 14px 35px rgba(2,8,23,.06)}}
  .qrfScoreHead{{display:flex;align-items:center;justify-content:space-between;gap:12px}}
  .qrfScoreTitle{{font-size:12px;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#64748b}}
  .qrfScoreValue{{font-size:36px;font-weight:950;line-height:1;color:#0f172a}}
  .qrfScoreValue small{{font-size:14px;color:#64748b}}
  .qrfScoreBar{{height:9px;margin-top:12px;border-radius:999px;background:#e5e7eb;overflow:hidden}}
  .qrfScoreBar span{{display:block;height:100%;width:0;background:linear-gradient(90deg,#7a0026,#10b981);transition:width .35s ease}}
  .qrfScoreCounts{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}}
  .qrfScoreCounts div{{padding:9px;border:1px solid rgba(2,8,23,.07);border-radius:13px;text-align:center;background:#fff}}
  .qrfScoreCounts b{{display:block;font-size:18px}}.qrfScoreCounts span{{font-size:11px;color:#64748b;font-weight:850}}
  .qrfScoreState{{margin-top:12px;font-size:13px;font-weight:850;color:#475569}}
  .qrfScoreState.blocked{{color:#991b1b}}.qrfScoreState.ready{{color:#166534}}
  .qrfScoreLink{{display:inline-flex;margin-top:12px;font-weight:850;text-decoration:none}}
  @media(prefers-reduced-motion:reduce){{.qrfScoreBar span{{transition:none}}}}
</style>
<script>
(function(){{
  const target=document.querySelector('.complianceHeroCard');
  if(!target || document.getElementById('qrf-score-widget')) return;
  const box=document.createElement('section');
  box.id='qrf-score-widget';
  box.className='qrfScoreWidget';
  box.setAttribute('aria-live','polite');
  box.innerHTML='<div class="qrfScoreTitle">Compliance Engine</div><div class="qrfScoreState">Calcolo in corso…</div>';
  target.prepend(box);

  fetch('/api/wines/{wine_id}/compliance-report',{{headers:{{'Accept':'application/json'}},credentials:'same-origin'}})
    .then(function(response){{if(!response.ok) throw new Error('HTTP '+response.status);return response.json();}})
    .then(function(report){{
      const counts=report.counts||{{}};
      const score=Math.max(0,Math.min(100,Number(report.score)||0));
      const blocked=!report.publishable;
      box.innerHTML=''
        +'<div class="qrfScoreHead"><div><div class="qrfScoreTitle">Compliance Score</div><div class="qrfScoreValue">'+score+'<small>/100</small></div></div></div>'
        +'<div class="qrfScoreBar" aria-hidden="true"><span style="width:'+score+'%"></span></div>'
        +'<div class="qrfScoreCounts">'
        +'<div><b>'+(counts.PASS||0)+'</b><span>PASS</span></div>'
        +'<div><b>'+(counts.WARNING||0)+'</b><span>WARNING</span></div>'
        +'<div><b>'+(counts.ERROR||0)+'</b><span>ERROR</span></div>'
        +'</div>'
        +'<div class="qrfScoreState '+(blocked?'blocked':'ready')+'">'
        +(blocked?'Sono presenti errori bloccanti.':'Nessun errore bloccante rilevato.')
        +' Revisione umana obbligatoria.</div>'
        +'<a class="qrfScoreLink" href="/app/wine/{wine_id}/compliance-report">Apri il report motivato →</a>';
    }})
    .catch(function(){{
      box.innerHTML='<div class="qrfScoreTitle">Compliance Engine</div><div class="qrfScoreState blocked">Score temporaneamente non disponibile. Apri il report dettagliato.</div><a class="qrfScoreLink" href="/app/wine/{wine_id}/compliance-report">Apri il report →</a>';
    }});
}})();
</script>
"""
