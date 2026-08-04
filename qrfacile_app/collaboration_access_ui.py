from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.collaboration_access import list_wine_access
from qrfacile_app.ui_shell import esc, page

router = APIRouter(tags=["collaboration-access"])


def _studio_options(studios: list[dict], current_id: int = 0) -> str:
    options = ["<option value=''>Scegli uno studio autorizzato</option>"]
    for studio in studios:
        name = studio.get("studio_name") or studio.get("email") or "Studio"
        edit_note = "può modificare" if studio.get("can_edit") else "solo vista"
        studio_id = int(studio['studio_user_id'])
        selected = " selected" if studio_id == int(current_id or 0) else ""
        current = " · attuale" if selected else ""
        options.append(f"<option value='{studio_id}'{selected}>{esc(str(name))} · {esc(edit_note)}{current}</option>")
    return "".join(options)


def _access_html(wine_id: int, data: dict, role: str) -> str:
    studios = data.get("studios") or []
    rows = []
    for item in data.get("labels") or []:
        label_id = int(item.get("label_id") or 0)
        assigned = bool(item.get("collaboration_id"))
        current_id = int(item.get("studio_user_id") or item.get("collaborator_user_id") or 0)
        studio_options = _studio_options(studios, current_id)
        studio = item.get("studio_name") or "Gestione diretta della cantina"
        permissions = []
        if assigned:
            if item.get("can_view"):
                permissions.append("vede")
            if item.get("can_edit"):
                permissions.append("modifica")
            if item.get("can_media"):
                permissions.append("gestisce immagini")
            if item.get("can_export"):
                permissions.append("esporta")
        permissions_text = ", ".join(permissions) if permissions else (
            "La cantina gestisce direttamente questa etichetta" if not assigned else "nessun permesso operativo"
        )
        status = f"Studio assegnato: {studio}" if assigned else "Gestione diretta della cantina"

        controls = ""
        if role in {"winery", "admin"}:
            if studios:
                controls = f"""
                <div class='accessControls'>
                  <form method='post' action='/app/label/{label_id}/acl/assign'>
                    <label>{'Cambia studio' if assigned else 'Assegna uno studio'}</label>
                    <select name='studio_user_id' required>{studio_options}</select>
                    <select name='profile'>
                      <option value='graphic' selected>Lavora su grafica e contenuti</option>
                      <option value='view'>Può soltanto vedere</option>
                    </select>
                    <button class='btn btn-primary' type='submit'>{'Cambia studio' if assigned else 'Assegna uno studio'}</button>
                  </form>
                  {f'''<form method='post' action='/app/label/{label_id}/acl/clear' onsubmit="return confirm('Rimuovere lo studio assegnato e passare alla gestione diretta? Lo studio e lo storico non saranno eliminati.');">
                    <button class='btn' type='submit'>Rimuovi studio assegnato · Gestisco io</button>
                  </form>''' if assigned else ''}
                </div>
                """
            else:
                controls = "<a class='btn btn-primary' href='/app/winery/settings#invite-studio'>Invita prima uno studio</a>"

        rows.append(f"""
        <article class='card accessLabelCard'>
          <div class='accessLabelTop'>
            <div>
              <div class='accessKicker'>Etichetta #{label_id}</div>
              <div class='h2'>{esc(str(item.get('label_type') or 'Etichetta'))}</div>
              <div class='p'>{esc(str(item.get('language') or ''))}</div>
            </div>
            <span class='accessStatus {'assigned' if assigned else ''}'>{'🏢' if assigned else '👤'} {esc(status)}</span>
          </div>
          <div class='accessWho'><b>{esc(status)}</b><span>{esc(permissions_text)}</span></div>
          <div class='accessRule'>Nessuno studio può pubblicare. La pubblicazione resta sempre riservata alla cantina.</div>
          {controls}
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
      .accessSteps{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:14px}}
      .accessSteps div{{padding:13px;border:1px solid var(--border);border-radius:14px;background:var(--card)}}
      .accessSteps b{{display:block}}.accessSteps span{{display:block;color:var(--muted);font-size:12px;margin-top:4px}}
      .accessGrid{{display:grid;gap:12px;margin-top:14px}}
      .accessLabelCard{{display:grid;gap:13px}}
      .accessLabelTop{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}}
      .accessKicker{{font-size:11px;font-weight:950;color:#0f766e;text-transform:uppercase;letter-spacing:.07em}}
      .accessStatus{{padding:7px 10px;border-radius:999px;background:#e2e8f0;color:#334155;font-size:12px;font-weight:900}}
      .accessStatus.assigned{{background:#dcfce7;color:#166534}}
      .accessWho{{display:grid;gap:4px;padding:14px;border-radius:14px;background:rgba(248,250,252,.86);border:1px solid var(--border)}}
      .accessWho span,.accessRule{{font-size:13px;color:var(--muted)}}
      .accessRule{{font-weight:850}}
      .accessControls{{display:flex;gap:10px;align-items:end;flex-wrap:wrap;padding-top:4px;border-top:1px solid var(--border)}}
      .accessControls form:first-child{{display:grid;grid-template-columns:minmax(210px,1fr) minmax(190px,1fr) auto;gap:8px;align-items:end;flex:1}}
      .accessControls label{{grid-column:1/-1;color:var(--muted);font-size:12px;font-weight:900}}
      @media(max-width:820px){{.accessHero,.accessSteps,.accessControls form:first-child{{grid-template-columns:1fr}}.accessControls{{align-items:stretch}}.accessControls form,.accessControls .btn{{width:100%}}}}
    </style>
    <div class='card accessHero'>
      <div>
        <div class='accessKicker'>Accessi e responsabilità</div>
        <div class='h1'>Chi lavora su ogni etichetta</div>
        <div class='p'>Tre passaggi semplici: autorizza lo studio alla cantina, assegnagli una singola etichetta, poi la cantina controlla e pubblica.</div>
        <div class='row' style='margin-top:14px'>
          <a class='btn' href='/app/winery/settings'>1. Studi autorizzati</a>
          <a class='btn' href='/app/wine/{int(wine_id)}'>Torna al vino</a>
        </div>
      </div>
      <div class='accessHeroPanel'>
        <div><span>Etichette</span><b>{len(data.get('labels') or [])}</b></div>
        <div><span>Studi disponibili</span><b>{len(studios)}</b></div>
        <div><span>Pubblicazione studio</span><b>Mai consentita</b></div>
      </div>
    </div>
    <div class='accessSteps'>
      <div><b>1. Collega</b><span>La cantina invita o autorizza uno studio.</span></div>
      <div><b>2. Assegna</b><span>Sceglie su quale etichetta può lavorare.</span></div>
      <div><b>3. Approva</b><span>La cantina verifica e pubblica il risultato.</span></div>
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
