import time
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, pill, esc

router = APIRouter()


def now() -> int:
    return int(time.time())


def _get_winery_id_for_user(cur, user_id: int) -> int:
    cur.execute("SELECT id FROM wineries WHERE owner_user_id=%s LIMIT 1", (int(user_id),))
    r = cur.fetchone()
    if not r:
        raise HTTPException(403, "Cantina non trovata per questo utente")
    return int(r["id"])


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))
    except Exception:
        return "-"


def _preset_name(can_view: bool, can_edit: bool, can_create: bool) -> str:
    if can_view and can_edit and can_create:
        return "Collaboratore completo"
    if can_view and can_edit and not can_create:
        return "Solo grafica"
    if can_view and (not can_edit) and (not can_create):
        return "Solo vista"
    return "Personalizzato"


def _access_mode(can_view: bool, can_edit: bool, can_create: bool) -> str:
    if can_edit or can_create:
        return "Puo modificare"
    if can_view:
        return "Solo vedere"
    return "Collegato senza operativita"


def _load_invites(cur, winery_id: int | None, role: str) -> list[dict]:
    if role == "admin" or winery_id is None:
        return []

    cur.execute(
        """
        SELECT
          token,
          studio_email,
          can_view,
          can_edit,
          can_create,
          created_at,
          expires_at,
          used_at
        FROM studio_invites
        WHERE winery_id=%s
        ORDER BY created_at DESC
        LIMIT 50
        """,
        (int(winery_id),),
    )
    return cur.fetchall() or []


def _active_invites(invites: list[dict]) -> list[dict]:
    ts = now()
    return [
        inv for inv in invites
        if not inv.get("used_at") and not (
            inv.get("expires_at") and int(inv.get("expires_at") or 0) < ts
        )
    ]


def _workflow_state(rows: list[dict], invites: list[dict]) -> tuple[str, str, int]:
    if not rows and not _active_invites(invites):
        return (
            "Nessuno studio collegato",
            "Invita uno studio quando vuoi aprire una collaborazione.",
            0,
        )
    if not rows:
        return (
            "Invito inviato",
            "Lo studio deve accettare l'invito prima di diventare operativo.",
            1,
        )
    if any(bool(r.get("can_edit")) or bool(r.get("can_create")) for r in rows):
        return (
            "Studio operativo",
            "Almeno uno studio collegato puo lavorare sulle etichette.",
            4,
        )
    if any(bool(r.get("can_view")) for r in rows):
        return (
            "Permessi attivi",
            "Lo studio collegato puo vedere le informazioni consentite.",
            3,
        )
    return (
        "Studio collegato",
        "Il collegamento esiste, ma i permessi operativi non sono attivi.",
        2,
    )


def _workflow_timeline(active_idx: int) -> str:
    steps = [
        ("Nessuno studio collegato", "Punto di partenza"),
        ("Invito inviato", "Email allo studio"),
        ("Studio collegato", "Invito accettato"),
        ("Permessi attivi", "Vista, modifica o creazione"),
        ("Studio operativo", "Pronto sulle etichette"),
    ]
    items = ""
    for idx, (label, detail) in enumerate(steps):
        state = "done" if idx < active_idx else ("active" if idx == active_idx else "")
        items += f"""
        <div class="wineryTimelineStep {state}">
          <span>{idx + 1}</span>
          <b>{esc(label)}</b>
          <small>{esc(detail)}</small>
        </div>
        """
    return f'<div class="wineryTimeline">{items}</div>'


def _invite_link(token: str) -> str:
    token = (token or "").strip()
    return f"/app/invite/studio/accept/{token}" if token else ""


def _invite_card(inv: dict) -> str:
    email = (inv.get("studio_email") or "").strip() or "-"
    token = (inv.get("token") or "").strip()
    invite_link = _invite_link(token)
    preset = _preset_name(
        bool(inv.get("can_view")),
        bool(inv.get("can_edit")),
        bool(inv.get("can_create")),
    )
    created = _fmt_ts(int(inv.get("created_at") or 0))
    expires = _fmt_ts(int(inv.get("expires_at") or 0))
    invite_actions = ""
    if invite_link:
        invite_actions = f"""
        <div class="wineryInviteActions">
          <button class="btn" type="button" data-copy="{esc(invite_link)}">Copia link invito</button>
          <a class="btn" href="{esc(invite_link)}" target="_blank" rel="noopener">Apri link invito</a>
        </div>
        """

    return f"""
    <article class="card wineryInvitePending">
      <div class="wineryInvitePendingMain">
        <div class="wineryStudioKicker">Invito in attesa</div>
        <div class="h2">{esc(email)}</div>
        <div class="p">Inviato il {esc(created)} · valido fino al {esc(expires)}</div>
        <div class="p wineryPendingExplain">Nessuno studio è ancora operativo: il collegamento nasce solo dopo l'accettazione.</div>
      </div>
      <div class="wineryInvitePendingMeta">
        {pill("Non ancora collegato", "blue")}
        <span>{esc(preset)}</span>
        {invite_actions}
      </div>
    </article>
    """


def _load_rows(cur, winery_id: int | None, role: str) -> list[dict]:
    if role == "admin" and winery_id is None:
        cur.execute(
            """
            SELECT
              sc.id,
              sc.winery_id,
              w.name AS winery_name,
              sc.studio_user_id,
              u.email AS studio_email,
              COALESCE(s.company_name,'') AS company_name,
              sc.can_view,
              sc.can_edit,
              sc.can_create,
              sc.created_at
            FROM studio_clients sc
            JOIN wineries w ON w.id = sc.winery_id
            JOIN users u ON u.id = sc.studio_user_id
            LEFT JOIN studios s ON s.user_id = u.id
            ORDER BY sc.created_at DESC
            LIMIT 300
            """
        )
        return cur.fetchall() or []

    cur.execute(
        """
        SELECT
          sc.id,
          sc.winery_id,
          w.name AS winery_name,
          sc.studio_user_id,
          u.email AS studio_email,
          COALESCE(s.company_name,'') AS company_name,
          sc.can_view,
          sc.can_edit,
          sc.can_create,
          sc.created_at
        FROM studio_clients sc
        JOIN wineries w ON w.id = sc.winery_id
        JOIN users u ON u.id = sc.studio_user_id
        LEFT JOIN studios s ON s.user_id = u.id
        WHERE sc.winery_id=%s
        ORDER BY sc.created_at DESC
        """,
        (int(winery_id),),
    )
    return cur.fetchall() or []


def _row_card(r: dict) -> str:
    preset = _preset_name(bool(r["can_view"]), bool(r["can_edit"]), bool(r["can_create"]))
    access_mode = _access_mode(bool(r["can_view"]), bool(r["can_edit"]), bool(r["can_create"]))
    created = _fmt_ts(int(r.get("created_at") or 0))
    sc_id = int(r["id"])
    studio_email = (r.get("studio_email") or "").strip() or "-"
    company_name = (r.get("company_name") or "").strip()
    winery_name = (r.get("winery_name") or "").strip() or "-"

    display_name = company_name if company_name else studio_email
    subline = studio_email if company_name else ""

    perm_items = [
        ("Vedere", "consulta etichette e materiali", bool(r.get("can_view"))),
        ("Modificare", "lavora su contenuti e grafica", bool(r.get("can_edit"))),
        ("Creare", "avvia nuove etichette", bool(r.get("can_create"))),
    ]
    perms_html = "".join(
        [
            f"""
            <span class="wineryPerm {'on' if enabled else 'off'}">
              <b>{esc(label)}</b>
              <small>{esc(detail if enabled else 'non consentito')}</small>
            </span>
            """
            for label, detail, enabled in perm_items
        ]
    )

    return f"""
    <article class="card wineryStudioCard">
      <div class="wineryStudioTop">
        <div class="wineryStudioIdentity">
          <div class="wineryStudioAvatar">SG</div>
          <div style="min-width:0;flex:1">
            <div class="wineryStudioKicker">Studio collegato</div>
            <div class="h2">{esc(display_name)}</div>
            {f'<div class="p wineryStudioEmail">{esc(subline)}</div>' if subline else ''}
          </div>
        </div>

        <div class="wineryStudioStatus">
          {pill("Collegamento attivo", "green")}
          <span>Dal {esc(created)}</span>
        </div>
      </div>

      <div class="wineryStudioBody">
        <div class="wineryStudioMeta">
          <div>
            <span>Accesso attuale</span>
            <b>{esc(access_mode)}</b>
          </div>
          <div>
            <span>Profilo permessi</span>
            <b>{esc(preset)}</b>
          </div>
          <div>
            <span>Cantina</span>
            <b>{esc(winery_name)}</b>
          </div>
        </div>

        <div class="wineryPermBox">
          <div class="wineryBoxTitle">Cosa puo fare lo studio</div>
          <div class="wineryPermGrid">
            {perms_html}
          </div>
          <div class="wineryControlNote">
            La cantina mantiene il controllo finale e puo revocare l'accesso in qualsiasi momento.
          </div>
        </div>
      </div>

      <div class="wineryStudioActions">
        <form method="post" action="/app/settings/studios/set" class="wineryPresetForm">
          <input type="hidden" name="sc_id" value="{sc_id}">
          <label>Gestisci permessi</label>
          <select name="preset">
            <option value="graphic">Solo grafica</option>
            <option value="full">Collaboratore completo</option>
            <option value="view">Solo vista</option>
          </select>
          <button class="btn" type="submit">Salva permessi</button>
        </form>

        <form method="post" action="/app/settings/studios/revoke" onsubmit="return confirm('Revocare il collegamento operativo a questo studio?');">
          <input type="hidden" name="sc_id" value="{sc_id}">
          <button class="btn wineryRevokeBtn" type="submit">Revoca accesso</button>
        </form>
      </div>
    </article>
    """


def _page_impl(request: Request, msg: str = "") -> HTMLResponse:
    user = require_any_role(request, ("winery", "admin"))
    uid = int(user.get("id") or user.get("user_id"))
    role = (user.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            winery_id = None
            winery_name = ""
            if role != "admin":
                winery_id = _get_winery_id_for_user(cur, uid)
                cur.execute("SELECT name FROM wineries WHERE id=%s LIMIT 1", (int(winery_id),))
                wr = cur.fetchone() or {}
                winery_name = (wr.get("name") or "").strip()

            rows = _load_rows(cur, winery_id, role)
            invites = _load_invites(cur, winery_id, role)

    actions = top_actions(
        ("/app/dashboard", "Dashboard"),
        ("/app/new-label", "Nuova etichetta"),
        ("/app/labels/search", "Ricerca"),
        ("/app/start", "Menu"),
        ("/logout", "Logout"),
    )

    msg_text = msg or ""
    msg_arg = msg_text if msg_text else ""

    active_invites = _active_invites(invites)
    workflow_title, workflow_copy, workflow_idx = _workflow_state(rows, invites)
    timeline_html = _workflow_timeline(workflow_idx)
    primary_cta_label = "Gestisci studio collegato" if rows else "Invita studio"
    primary_cta_href = "#studios-collegati" if rows else "#invite-studio"
    latest_invite_link = _invite_link(active_invites[0].get("token") or "") if active_invites else ""
    secondary_cta_html = ""
    if not rows and latest_invite_link:
        secondary_cta_html = f'<button class="btn" type="button" data-copy="{esc(latest_invite_link)}">Copia link ultimo invito</button>'
    linked_section_title = "Nessuno studio collegato"
    if rows:
        linked_section_title = "Studio collegato" if len(rows) == 1 else "Studi collegati"

    if role == "admin":
        title = "QRFACILE · Studi grafici autorizzati"
        subtitle = "Admin · Studi grafici autorizzati"
        intro = """
        <div class="p">
          Vista admin dei collegamenti tra cantine e studi. Ogni card mostra chi e collegato,
          da quando e con quali permessi.
        </div>
        """
    else:
        title = "QRFACILE · Impostazioni Cantina"
        subtitle = "Cantina · Studi grafici autorizzati"
        intro = f"""
        <div class="p">
          La cantina <b>{esc(winery_name or '-')}</b> decide chi entra, cosa puo fare e puo
          revocare sempre l'accesso. Lo studio collabora, la cantina mantiene il controllo finale.
        </div>
        """

    if rows:
        cards = "".join(_row_card(r) for r in rows)
    else:
        cards = """
        <div class="card wineryEmptyCard">
          <div class="h2">Nessuno studio collegato</div>
          <div class="p">
            Qui compariranno nome studio, data collegamento, permessi e revoca accesso.
          </div>
        </div>
        """

    pending_invites_html = "".join(_invite_card(i) for i in active_invites)
    if pending_invites_html:
        pending_invites_html = f"""
        <div class="wineryPendingList">
          <div class="wineryStudioKicker">Inviti in attesa</div>
          {pending_invites_html}
        </div>
        """

    invite_box = ""
    if role != "admin":
        invite_btn_class = "btn btn-primary" if not rows else "btn"
        invite_btn_label = "Invita studio" if not rows else "Invia altro invito"
        invite_box = f"""
        <div class="card wineryInviteBox" id="invite-studio">
          <div class="wineryStudioKicker">Nuova collaborazione</div>
          <div class="h2">Invita uno studio</div>
          <div class="p" style="margin-top:8px">
            Scegli l'email e i permessi iniziali. Dopo l'accettazione potrai cambiarli o revocarli.
          </div>
          <form method="post" action="/app/settings/studios/invite" class="wineryInviteForm">
            <div>
              <label>Email studio</label>
              <input class="input" type="email" name="studio_email" placeholder="studio@grafica.it" required>
            </div>
            <div>
              <label>Permessi iniziali</label>
              <select name="preset">
                <option value="view">Solo vista</option>
                <option value="graphic" selected>Solo grafica</option>
                <option value="full">Collaboratore completo</option>
              </select>
            </div>
            <button class="{invite_btn_class}" type="submit">{invite_btn_label}</button>
          </form>
        </div>
        """

    body = f"""
    <section class="wineryStudioWrap">
      <div class="card wineryStudioHero">
        <div>
          <div class="wineryStudioKicker">Workflow Cantina ↔ Studio</div>
          <div class="h1">{esc(workflow_title)}</div>
          <div class="p wineryWorkflowCopy">{esc(workflow_copy)}</div>
          {intro}
          <div class="wineryHeroActions">
            <a class="btn btn-primary" href="{esc(primary_cta_href)}">{esc(primary_cta_label)}</a>
            {secondary_cta_html}
          </div>
        </div>

        <div class="wineryHeroPanel">
          <div><span>Studi collegati</span><b>{len(rows)}</b></div>
          <div><span>Inviti in attesa</span><b>{len(active_invites)}</b></div>
          <div><span>Controllo finale</span><b>Cantina</b></div>
        </div>
      </div>

      <div class="card wineryTimelineCard">
        <div class="wineryStudioKicker">Avanzamento</div>
        {timeline_html}
      </div>

      <div class="wineryControlGrid">
        <div class="note">
          <b>Chi e collegato</b><br>
          Nome studio, email e data sono sempre visibili nella card del collegamento.
        </div>
        <div class="note">
          <b>Cosa puo fare</b><br>
          I permessi distinguono chiaramente vedere, modificare e creare.
        </div>
        <div class="note">
          <b>Revoca sempre disponibile</b><br>
          La cantina puo interrompere il collegamento in qualsiasi momento.
        </div>
      </div>

      {pending_invites_html}
      {invite_box}

      <div class="card winerySectionHead" id="studios-collegati">
        <div>
          <div class="wineryStudioKicker">Collegamenti operativi</div>
          <div class="h2">{esc(linked_section_title)}</div>
        </div>
        <div class="wineryTotal">Totale: <b>{len(rows)}</b></div>
      </div>

      <div class="wineryStudioList">
        {cards}
      </div>
    </section>

    <style>
      .wineryStudioWrap {{ max-width:1180px; margin:0 auto; }}
      .wineryStudioHero {{ margin-top:14px; display:grid; grid-template-columns:minmax(0,1fr) 340px; gap:22px; align-items:center; background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(248,252,250,.94)); border:1px solid rgba(2,8,23,.08); }}
      .wineryStudioKicker {{ color:#0f766e; font-size:12px; font-weight:950; letter-spacing:.08em; text-transform:uppercase; margin-bottom:6px; }}
      .wineryWorkflowCopy {{ margin-top:8px; font-weight:850; color:#0f172a; }}
      .wineryHeroActions {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:14px; }}
      .wineryHeroPanel {{ display:grid; gap:10px; }}
      .wineryHeroPanel div, .wineryStudioMeta div {{ border:1px solid rgba(2,8,23,.07); background:rgba(255,255,255,.78); border-radius:14px; padding:14px; }}
      .wineryHeroPanel span, .wineryStudioMeta span {{ display:block; color:#64748b; font-size:12px; font-weight:900; }}
      .wineryHeroPanel b, .wineryStudioMeta b {{ display:block; margin-top:5px; color:#0f172a; font-size:18px; font-weight:950; }}
      .wineryTimelineCard {{ margin-top:14px; }}
      .wineryTimeline {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:8px; }}
      .wineryTimelineStep {{ position:relative; border:1px solid rgba(2,8,23,.08); border-radius:14px; padding:12px; background:#fff; min-height:96px; }}
      .wineryTimelineStep span {{ width:26px; height:26px; border-radius:999px; display:flex; align-items:center; justify-content:center; background:#e2e8f0; color:#334155; font-size:12px; font-weight:950; }}
      .wineryTimelineStep b {{ display:block; margin-top:10px; color:#0f172a; font-size:13px; font-weight:950; }}
      .wineryTimelineStep small {{ display:block; margin-top:4px; color:#64748b; font-size:11px; font-weight:800; line-height:1.35; }}
      .wineryTimelineStep.done span, .wineryTimelineStep.active span {{ background:#0f766e; color:#fff; }}
      .wineryTimelineStep.active {{ border-color:rgba(15,118,110,.32); background:rgba(240,253,250,.82); }}
      .wineryControlGrid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:14px; }}
      .wineryInviteBox, .winerySectionHead, .wineryPendingList {{ margin-top:14px; }}
      .wineryInviteForm {{ display:grid; grid-template-columns:minmax(220px,1fr) 260px auto; gap:10px; align-items:end; margin-top:14px; }}
      .wineryInviteForm label {{ display:block; margin-bottom:6px; color:#64748b; font-size:12px; font-weight:950; }}
      .wineryInvitePending {{ display:flex; justify-content:space-between; gap:14px; align-items:center; margin-top:8px; }}
      .wineryInvitePendingMain {{ min-width:0; }}
      .wineryPendingExplain {{ margin-top:6px; font-weight:850; color:#0f172a; }}
      .wineryInvitePendingMeta {{ display:grid; gap:8px; justify-items:end; color:#64748b; font-size:12px; font-weight:900; }}
      .wineryInviteActions {{ display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }}
      .winerySectionHead {{ display:flex; justify-content:space-between; gap:14px; align-items:center; flex-wrap:wrap; }}
      .wineryTotal {{ color:#64748b; font-size:13px; font-weight:900; }}
      .wineryStudioList {{ display:grid; gap:12px; margin-top:12px; }}
      .wineryStudioCard {{ padding:0; overflow:hidden; }}
      .wineryStudioTop {{ display:flex; justify-content:space-between; gap:14px; align-items:flex-start; flex-wrap:wrap; padding:16px; border-bottom:1px solid rgba(2,8,23,.07); }}
      .wineryStudioIdentity {{ display:flex; gap:14px; align-items:center; min-width:0; flex:1; }}
      .wineryStudioAvatar {{ width:54px; height:54px; border-radius:16px; display:flex; align-items:center; justify-content:center; flex:0 0 auto; background:linear-gradient(135deg,rgba(191,245,230,.86),rgba(207,232,255,.82)); color:#0f766e; font-weight:950; border:1px solid rgba(2,8,23,.07); }}
      .wineryStudioEmail {{ margin-top:4px; }}
      .wineryStudioStatus {{ display:grid; gap:6px; justify-items:end; color:#64748b; font-size:12px; font-weight:800; }}
      .wineryStudioBody {{ display:grid; grid-template-columns:280px minmax(0,1fr); gap:14px; padding:16px; }}
      .wineryStudioMeta {{ display:grid; gap:10px; }}
      .wineryPermBox {{ border:1px solid rgba(2,8,23,.07); border-radius:14px; padding:14px; background:rgba(248,250,252,.78); }}
      .wineryBoxTitle {{ font-size:12px; font-weight:950; color:#0f766e; letter-spacing:.07em; text-transform:uppercase; }}
      .wineryPermGrid {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:10px; }}
      .wineryPerm {{ border:1px solid rgba(2,8,23,.07); background:#fff; border-radius:12px; padding:12px; min-height:76px; }}
      .wineryPerm b {{ display:block; font-size:13px; font-weight:950; color:#0f172a; }}
      .wineryPerm small {{ display:block; margin-top:4px; font-size:11px; font-weight:900; color:#64748b; line-height:1.35; }}
      .wineryPerm.on {{ border-color:rgba(20,184,166,.18); background:rgba(236,253,245,.78); }}
      .wineryPerm.off {{ opacity:.68; }}
      .wineryControlNote {{ margin-top:12px; color:#475569; font-size:12px; font-weight:850; line-height:1.45; }}
      .wineryStudioActions {{ display:flex; justify-content:space-between; gap:12px; align-items:center; flex-wrap:wrap; padding:16px; border-top:1px solid rgba(2,8,23,.07); }}
      .wineryPresetForm {{ display:flex; gap:8px; flex-wrap:wrap; align-items:end; }}
      .wineryPresetForm label {{ width:100%; margin:0; color:#64748b; font-size:12px; font-weight:950; }}
      .wineryRevokeBtn {{ border-color:rgba(239,68,68,.22); color:#b91c1c; background:rgba(254,242,242,.78); }}
      .wineryEmptyCard {{ margin-top:12px; }}
      @media(max-width:980px) {{ .wineryStudioHero, .wineryStudioBody, .wineryControlGrid, .wineryInviteForm, .wineryTimeline {{ grid-template-columns:1fr; }} .wineryStudioStatus, .wineryInvitePendingMeta {{ justify-items:start; }} }}
      @media(max-width:620px) {{ .wineryPermGrid {{ grid-template-columns:1fr; }} .wineryPresetForm .btn, .wineryPresetForm select, .wineryStudioActions form, .wineryRevokeBtn, .wineryInviteForm .btn, .wineryHeroActions .btn, .wineryInviteActions .btn {{ width:100%; }} .wineryInvitePending {{ align-items:flex-start; flex-direction:column; }} .wineryInviteActions, .wineryInvitePendingMeta {{ width:100%; justify-items:stretch; justify-content:stretch; }} }}
    </style>
    <script>
      document.addEventListener('click', function (event) {{
        var btn = event.target.closest('[data-copy]');
        if (!btn) return;
        var value = btn.getAttribute('data-copy') || '';
        if (!value) return;
        var absolute = value.indexOf('http') === 0 ? value : window.location.origin + value;
        function done() {{
          var old = btn.textContent;
          btn.textContent = 'Link copiato';
          window.setTimeout(function () {{ btn.textContent = old; }}, 1600);
        }}
        if (navigator.clipboard && navigator.clipboard.writeText) {{
          navigator.clipboard.writeText(absolute).then(done);
          return;
        }}
        var input = document.createElement('input');
        input.value = absolute;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        done();
      }});
    </script>
    """


    return HTMLResponse(page(
        title=title,
        subtitle=subtitle,
        body_html=body,
        actions_html=actions,
        msg=msg_arg,
        err="",
        user_email=user.get("email", ""),
        role=role,
        credits=None,
    ))


@router.get("/app/settings/studios")
def studios_settings_redirect(msg: str = ""):
    suffix = f"?msg={msg}" if msg else ""
    return RedirectResponse(f"/app/winery/settings{suffix}", status_code=303)


@router.get("/app/winery/settings", response_class=HTMLResponse)
def winery_settings_page(request: Request, msg: str = ""):
    return _page_impl(request, msg=msg)


@router.post("/app/settings/studios/set")
def studios_set_preset(request: Request, sc_id: int = Form(...), preset: str = Form(...)):
    user = require_any_role(request, ("winery", "admin"))
    uid = int(user.get("id") or user.get("user_id"))
    role = (user.get("role") or "").lower().strip()

    preset = (preset or "").strip().lower()
    if preset == "full":
        can_view, can_edit, can_create = True, True, True
    elif preset == "graphic":
        can_view, can_edit, can_create = True, True, False
    elif preset == "view":
        can_view, can_edit, can_create = True, False, False
    else:
        raise HTTPException(400, "Preset non valido")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if role != "admin":
                winery_id = _get_winery_id_for_user(cur, uid)
                cur.execute("SELECT winery_id FROM studio_clients WHERE id=%s LIMIT 1", (int(sc_id),))
                r = cur.fetchone()
                if not r or int(r["winery_id"]) != int(winery_id):
                    raise HTTPException(403, "Non autorizzato")

            cur.execute(
                """
                UPDATE studio_clients
                SET can_view=%s, can_edit=%s, can_create=%s
                WHERE id=%s
                """,
                (can_view, can_edit, can_create, int(sc_id)),
            )
            conn.commit()

    return RedirectResponse("/app/winery/settings?msg=Permessi%20aggiornati", status_code=303)


@router.post("/app/settings/studios/revoke")
def studios_revoke(request: Request, sc_id: int = Form(...)):
    user = require_any_role(request, ("winery", "admin"))
    uid = int(user.get("id") or user.get("user_id"))
    role = (user.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if role != "admin":
                winery_id = _get_winery_id_for_user(cur, uid)
                cur.execute("SELECT winery_id FROM studio_clients WHERE id=%s LIMIT 1", (int(sc_id),))
                r = cur.fetchone()
                if not r or int(r["winery_id"]) != int(winery_id):
                    raise HTTPException(403, "Non autorizzato")

            cur.execute("DELETE FROM studio_clients WHERE id=%s", (int(sc_id),))
            conn.commit()

    return RedirectResponse("/app/winery/settings?msg=Collegamento%20revocato", status_code=303)

