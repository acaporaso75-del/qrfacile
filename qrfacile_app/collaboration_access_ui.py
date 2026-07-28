from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.collaboration_access import list_wine_access
from qrfacile_app.ui_shell import esc, page

router = APIRouter(tags=["collaboration-access"])


def _access_html(wine_id: int, data: dict, role: str) -> str:
    rows = []
    for item in data.get("labels") or []:
        assigned = bool(item.get("collaboration_id"))
        studio = item.get("studio_name") or "Gestione interna cantina"
        if assigned:
            permissions = []
            if item.get("can_view"):
                permissions.append("vede")
            if item.get("can_edit"):
                permissions.append("modifica")
            if item.get("can_media"):
                permissions.append("gestisce immagini")
            if item.get("can_export"):
                permissions.append("esporta")
            permissions_text = ", ".join(permissions) or "nessun permesso operativo"
            status = "Studio autorizzato"
        else:
            permissions_text = "La cantina gestisce direttamente questa etichetta"
            status = "Gestione interna"

        rows.append(f"""
        <article class='card accessLabelCard'>
          <div class='accessLabelTop'>
            <div>
              <div class='accessKicker'>Etichetta #{int(item.get('label_id') or 0)}</div>
              <div class='h2'>{esc(str(item.get('label_type') or 'Etichetta'))}</div>
              <div class='p'>{esc(str(item.get('language') or ''))}</div>
            </div>
            <span class='accessStatus {'assigned' if assigned else ''}'>{esc(status)}</span>
          </div>
          <div class='accessWho'><b>{esc(str(studio))}</b><span>{esc(permissions_text)}</span></div>
          <div class='accessRule'>La pubblicazione resta sempre riservata alla cantina o all’amministratore.</div>
          {f"<a class='btn' href='/app/label/{int(item.get('label_id') or 0)}/acl'>Modifica assegnazione</a>" if role in {'winery','admin'} else ''}
        </article>
        """)

    empty = "<div class='card'><div class='p'>Nessuna etichetta disponibile per questo vino.</div></div>" if not rows else ""
    return f"""
    <style>
      .accessHero{{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:18px;align-items:center}}
      .accessHeroPanel{{display:grid;gap:10px}}
      .accessHeroPanel div{{padding:14px;border-radius:15px;border:1px solid var(--border);background:var(--card)}}
      .accessHeroPanel span{{display:block;color:var(--muted);font-size:12px;font-weight:900}}
      .accessHeroPanel b{{display:block;margin-top:5px;font-size:20px}}
      .accessGrid{{display:grid;gap:12px;margin-top:14px}}
      .accessLabelCard{{display:grid;gap:13px}}
      .accessLabelTop{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}}
      .accessKicker{{font-size:11px;font-weight:950;color:#0f766e;text-transform:uppercase;letter-spacing:.07em}}
      .accessStatus{{padding:7px 10px;border-radius:999px;background:#e2e8f0;color:#334155;font-size:12px;font-weight:900}}
      .accessStatus.assigned{{background:#dcfce7;color:#166534}}
      .accessWho{{display:grid;gap:4px;padding:14px;border-radius:14px;background:rgba(248,250,252,.86);border:1px solid var(--border)}}
      .accessWho span,.accessRule{{font-size:13px;color:var(--muted)}}
      .accessRule{{font-weight:850}}
      @media(max-width:820px){{.accessHero{{grid-template-columns:1fr}}}}
    </style>
    <div class='card accessHero'>
      <div>
        <div class='accessKicker'>Accessi e responsabilità</div>
        <div class='h1'>Chi può lavorare sulle etichette</div>
        <div class='p'>La cantina collega uno studio, poi decide etichetta per etichetta cosa può vedere e modificare. Nessuno studio può pubblicare.</div>
        <div class='row' style='margin-top:14px'>
          <a class='btn' href='/app/winery/settings'>Studi autorizzati</a>
          <a class='btn' href='/app/wine/{int(wine_id)}'>Torna al vino</a>
        </div>
      </div>
      <div class='accessHeroPanel'>
        <div><span>Etichette</span><b>{len(data.get('labels') or [])}</b></div>
        <div><span>Controllo finale</span><b>Cantina</b></div>
        <div><span>Pubblicazione studio</span><b>Mai consentita</b></div>
      </div>
    </div>
    <div class='accessGrid'>{''.join(rows)}{empty}</div>
    """


@router.get("/api/wines/{wine_id}/access", response_class=JSONResponse)
def wine_access_api(request: Request, wine_id: int):
    user = require_any_role(request, ("admin", "winery", "studio"))
    return JSONResponse(list_wine_access(user, wine_id))


@router.get("/app/wine/{wine_id}/access-center", response_class=HTMLResponse)
def wine_access_center(request: Request, wine_id: int):
    user = require_any_role(request, ("admin", "winery", "studio"))
    data = list_wine_access(user, wine_id)
    role = str(user.get("role") or "").lower()
    return HTMLResponse(page(request, user, "Accessi etichette", _access_html(wine_id, data, role)))
