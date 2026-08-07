from __future__ import annotations

import os
import secrets
import smtplib
import time
from email.message import EmailMessage
from urllib.parse import quote_plus

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.checkout_ui import paypal_checkout_form, paypal_checkout_script
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, pill, esc

router = APIRouter()


def now() -> int:
    return int(time.time())


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))
    except Exception:
        return "-"


def _clean_email(email: str) -> str:
    """
    Rimuove spazi e caratteri invisibili.
    Esempio: 'acaporaso75 @gmail.com' -> 'acaporaso75@gmail.com'
    """
    return "".join((email or "").split()).strip().lower()


def _smtp_cfg():
    host = (os.getenv("SMTP_HOST", "") or "").strip()
    port = int((os.getenv("SMTP_PORT", "465") or "465").strip())
    user = (os.getenv("SMTP_USER", "") or "").strip()
    pwd = (os.getenv("SMTP_PASS", "") or "").strip()
    from_email = (
        (os.getenv("SMTP_FROM", "") or "").strip()
        or (os.getenv("FROM_EMAIL", "") or "").strip()
        or user
    )

    if not host or not user or not pwd or not from_email:
        return None

    return host, port, user, pwd, from_email


def _send_winery_invite_email(
    *,
    to_email: str,
    invite_link: str,
    studio_email: str,
    recommended_pack_label: str = "",
) -> tuple[bool, str]:
    """
    Invia email di invito da Studio -> Cantina.

    Non deve mai bloccare il flusso: se fallisce, l'invito resta creato
    e il link è copiabile dalla pagina Studio.
    """
    cfg = _smtp_cfg()
    if not cfg:
        return False, "SMTP non configurato"

    host, port, user, pwd, from_email = cfg

    subject = "Invito QRFACILE per gestire i QR delle etichette vino"

    pack_text = ""
    if recommended_pack_label and recommended_pack_label != "-":
        pack_text = f"\nPiano suggerito dallo studio: {recommended_pack_label}\n"

    body = f"""Buongiorno,

lo studio grafico {studio_email} ti ha invitato su QRFACILE.

QRFACILE è la piattaforma per gestire in modo ordinato le etichette digitali e i QR code dei vini:
- lotti
- dati obbligatori
- ingredienti, allergeni, valori nutrizionali e riciclo
- QR pronti per la stampa
- collaborazione tra cantina e studio grafico
{pack_text}
Per registrarti e collegare la tua cantina allo studio, apri questo link:

{invite_link}

Se non hai richiesto questo invito, puoi ignorare questa email.

QRFACILE
Il QR del vino, fatto semplice.
"""

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=25) as s:
                s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=25) as s:
                s.starttls()
                s.login(user, pwd)
                s.send_message(msg)

        return True, ""
    except Exception as e:
        return False, str(e)


def _thumb_for_winery(cur, winery_id: int) -> str:
    """
    Se in futuro avrai logo_path in wineries lo usa, altrimenti placeholder.
    """
    try:
        cur.execute("SELECT logo_path FROM wineries WHERE id=%s LIMIT 1", (int(winery_id),))
        r = cur.fetchone() or {}
        lp = (r.get("logo_path") or "").strip()
        if lp:
            return f"/uploads/{lp}"
    except Exception:
        pass
    return "/static/img/placeholder_label.svg"


def _studio_can_access_winery(cur, studio_user_id: int, winery_id: int) -> dict | None:
    cur.execute(
        """
        SELECT sc.can_view, sc.can_edit, sc.can_create, COALESCE(sc.recommended_pack, '') AS recommended_pack, w.name
        FROM studio_clients sc
        JOIN wineries w ON w.id = sc.winery_id
        WHERE sc.studio_user_id=%s AND sc.winery_id=%s
        LIMIT 1
        """,
        (int(studio_user_id), int(winery_id)),
    )
    return cur.fetchone()


def _pack_label(value: str, compact: bool = False) -> str:
    value = (value or "").strip().lower()
    if compact:
        labels = {
            "start": "Start",
            "pro": "Cantina",
            "plus": "Business",
            "unlimited": "Legacy",
        }
    else:
        labels = {
            "start": "Start · 20 crediti · €29",
            "pro": "Cantina · 60 crediti · €79",
            "plus": "Business · 200 crediti · €199",
            "unlimited": "Non disponibile online",
        }
    return labels.get(value, "Da valutare" if compact else "-")


def _invite_status(invite: dict) -> tuple[str, str]:
    if invite.get("used_at"):
        return "Collegato", "green"

    exp = invite.get("expires_at")
    if exp and int(exp) < now():
        return "Scaduto", "warn"

    return "In attesa", "blue"


@router.get("/studio", response_class=HTMLResponse)
def studio_dashboard(request: Request, msg: str = "", err: str = ""):
    user = require_any_role(request, ("studio", "admin"))
    uid = int(user["id"])
    role = (user.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if role == "admin":
                cur.execute(
                    """
                    SELECT
                      w.id AS winery_id,
                      w.name AS winery_name,
                      TRUE AS can_view,
                      TRUE AS can_edit,
                      TRUE AS can_create,
                      COUNT(DISTINCT qw.id) AS wines_count,
                      COUNT(DISTINCT wl.id) AS labels_count,
                      COALESCE(SUM(CASE WHEN wl.public_enabled THEN 1 ELSE 0 END),0) AS labels_public
                    FROM wineries w
                    LEFT JOIN qr_wines qw ON qw.winery_id = w.id
                    LEFT JOIN wine_labels wl ON wl.winery_id = w.id
                    GROUP BY w.id, w.name
                    ORDER BY lower(w.name)
                    LIMIT 300
                    """
                )
                wineries = cur.fetchall() or []

                cur.execute(
                    """
                    SELECT token, winery_id, studio_email, recommended_pack, created_at, expires_at, used_at
                    FROM studio_invites
                    ORDER BY created_at DESC
                    LIMIT 50
                    """
                )
                invites = cur.fetchall() or []
            else:
                cur.execute(
                    """
                    SELECT
                      w.id AS winery_id,
                      w.name AS winery_name,
                      sc.can_view, sc.can_edit, sc.can_create, COALESCE(sc.recommended_pack, '') AS recommended_pack,
                      COUNT(DISTINCT qw.id) AS wines_count,
                      COUNT(DISTINCT wl.id) AS labels_count,
                      COALESCE(SUM(CASE WHEN wl.public_enabled THEN 1 ELSE 0 END),0) AS labels_public
                    FROM studio_clients sc
                    JOIN wineries w ON w.id = sc.winery_id
                    LEFT JOIN qr_wines qw ON qw.winery_id = w.id
                    LEFT JOIN wine_labels wl ON wl.winery_id = w.id
                    WHERE sc.studio_user_id = %s
                    GROUP BY w.id, w.name, sc.can_view, sc.can_edit, sc.can_create, sc.recommended_pack
                    ORDER BY lower(w.name)
                    """,
                    (uid,),
                )
                wineries = cur.fetchall() or []

                cur.execute(
                    """
                    SELECT token, winery_id, studio_email, recommended_pack, created_at, expires_at, used_at
                    FROM studio_invites
                    WHERE inviter_user_id=%s
                    ORDER BY created_at DESC
                    LIMIT 50
                    """,
                    (uid,),
                )
                invites = cur.fetchall() or []

    actions = top_actions(
        ("/app/start", "Menu"),
        ("/app/billing", "Crediti"),
        ("/studio/settings", "Profilo Studio"),
        ("/logout", "Logout"),
    )

    total_wineries = len(wineries)
    active_invites = len([i for i in invites if not i.get("used_at") and not (i.get("expires_at") and int(i.get("expires_at") or 0) < now())])
    total_public_labels = sum(int(w.get("labels_public") or 0) for w in wineries)
    total_labels = sum(int(w.get("labels_count") or 0) for w in wineries)
    suggested_packs = [(w.get("recommended_pack") or "").strip().lower() for w in wineries if (w.get("recommended_pack") or "").strip()]
    suggested_plan = _pack_label(suggested_packs[0], compact=True) if suggested_packs else "Da valutare"

    cards_html = ""
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur2:
            for w in wineries:
                wid = int(w["winery_id"])
                thumb = _thumb_for_winery(cur2, wid)
                wines_n = int(w.get("wines_count") or 0)
                labels_n = int(w.get("labels_count") or 0)
                pub_n = int(w.get("labels_public") or 0)
                draft_n = max(labels_n - pub_n, 0)

                perm_txt = []
                perm_txt.append("vista" if w.get("can_view") else "no vista")
                perm_txt.append("modifica" if w.get("can_edit") else "no modifica")
                perm_txt.append("creazione" if w.get("can_create") else "no creazione")

                rp = (w.get("recommended_pack") or "").strip().lower()
                rp_label = _pack_label(rp, compact=True)

                cards_html += f"""
                <article class="card studioClientCard">
                  <div class="studioClientMain">
                    <div class="studioClientIdentity">
                      <img src="{thumb}" alt="" class="studioClientThumb">
                      <div style="min-width:0;flex:1">
                        <div class="studioClientKicker">Workspace cantina</div>
                        <div class="h2">{esc(w.get("winery_name") or f"Cantina {wid}")}</div>
                        <div class="studioPerms mono">{esc(" · ".join(perm_txt))}</div>
                      </div>
                    </div>

                    <div class="studioClientMetrics">
                      <div><span>Vini</span><b>{wines_n}</b></div>
                      <div><span>Etichette</span><b>{labels_n}</b></div>
                      <div><span>Pubbliche</span><b>{pub_n}</b></div>
                      <div><span>Bozze</span><b>{draft_n}</b></div>
                    </div>

                    <div class="studioClientSide">
                      {pill(f"Piano {rp_label}", "blue" if rp else "muted")}
                      <a class="btn btn-primary" href="/studio/winery/{wid}">Apri workspace</a>
                    </div>
                  </div>
                </article>
                """

    base_url = ""
    try:
        base_url = (getattr(request.app.state, "app_base_url", "") or "").rstrip("/")
    except Exception:
        base_url = ""

    if not base_url:
        try:
            host = request.headers.get("host", "")
            scheme = request.url.scheme
            if host:
                base_url = f"{scheme}://{host}".rstrip("/")
        except Exception:
            base_url = ""

    inv_rows = ""
    for i in invites:
        token = (i.get("token") or "").strip()
        status, status_tone = _invite_status(i)
        winery_id = i.get("winery_id")
        invite_path = f"/register-winery?invite={token}" if token else ""
        invite_url = f"{base_url}{invite_path}" if base_url and invite_path else invite_path

        recommended_pack = (i.get("recommended_pack") or "").strip().lower()
        recommended_label = _pack_label(recommended_pack)

        copy_btn = ""
        if token and not i.get("used_at"):
            copy_btn = """
            <button type="button" class="btn" style="padding:8px 12px;border-radius:12px"
              onclick="qrfCopyInvite(this)">
              Copia link invito
            </button>
            """

        inv_rows += f"""
        <tr>
          <td>
            <div class="qrfInviteCopyWrap studioInviteLinkBox">
              <input class="input qrfInviteCopyInput" readonly value="{esc(invite_url or token)}"
                onclick="this.focus();this.select();this.setSelectionRange(0, 99999);">
              <div class="studioInviteActions">
                {copy_btn}
                {f'<a class="btn" href="{esc(invite_path)}" target="_blank">Apri registrazione</a>' if invite_path else ''}
              </div>
            </div>
          </td>
          <td>{esc(i.get("studio_email") or "")}</td>
          <td>{esc(recommended_label)}</td>
          <td>{esc(_fmt_ts(i.get("created_at")))}</td>
          <td>{esc(_fmt_ts(i.get("expires_at")))}</td>
          <td>{pill(status, status_tone)}</td>
          <td>{esc(str(winery_id) if winery_id else "-")}</td>
        </tr>
        """

    body = f"""
    <script>
      function qrfCopyInvite(btn) {{
        const wrap = btn.closest('.qrfInviteCopyWrap');
        const input = wrap ? wrap.querySelector('.qrfInviteCopyInput') : null;

        if (!input) {{
          alert('Campo link non trovato.');
          return;
        }}

        input.focus();
        input.select();
        input.setSelectionRange(0, 99999);

        const text = input.value || '';

        function ok() {{
          btn.innerText = 'Copiato';
          setTimeout(function() {{ btn.innerText = 'Copia link invito'; }}, 1800);
        }}

        if (navigator.clipboard && window.isSecureContext) {{
          navigator.clipboard.writeText(text).then(ok).catch(function() {{
            try {{
              document.execCommand('copy');
              ok();
            }} catch(e) {{
              btn.innerText = 'Selezionato';
              alert('Il browser ha bloccato la copia automatica. Il link è selezionato: copialo manualmente.');
            }}
          }});
        }} else {{
          try {{
            document.execCommand('copy');
            ok();
          }} catch(e) {{
            btn.innerText = 'Selezionato';
            alert('Il browser ha bloccato la copia automatica. Il link è selezionato: copialo manualmente.');
          }}
        }}
      }}
    </script>

    <section class="studioConsole">
      <div class="studioHero card">
        <div>
          <div class="studioKicker">Console partner</div>
          <div class="h1">Area Studio</div>
          <div class="p">
            Gestisci cantine, inviti e workspace operativi da un’unica console.
          </div>
          <div class="studioHeroActions">
            <a class="btn btn-primary" href="#studio-invite-form">Invita una cantina</a>
            <a class="btn" href="/studio/settings">Profilo Studio</a>
          </div>
        </div>

        <div class="studioHeroStats">
          <div><span>Cantine collegate</span><b>{total_wineries}</b></div>
          <div><span>Inviti attivi</span><b>{active_invites}</b></div>
          <div><span>Etichette pubblicate</span><b>{total_public_labels}</b></div>
          <div><span>Piano suggerito</span><b>{esc(suggested_plan)}</b></div>
        </div>
      </div>

      <details class="studioGuide card">
        <summary>Guida rapida inviti e collegamento cantina</summary>
        <div class="p" style="margin-top:10px;line-height:1.55">
          Crea l’invito, QRFACILE prova a inviare l’email e mantiene sempre il link copiabile.
          Quando la cantina si registra dal link, il collegamento allo Studio viene creato automaticamente.
        </div>
        <div class="note studioGuideNote">
          Testo manuale: Ti invito su QRFACILE per gestire in modo ordinato etichette digitali e QR dei tuoi vini. Registrati dal link invito.
        </div>
      </details>

      <div class="card" id="studio-invite-form" style="margin-top:14px">
        <div class="studioSectionHead">
          <div>
            <div class="studioKicker">Nuovo cliente</div>
            <div class="h2">Invita una cantina</div>
          </div>
          <a class="btn" href="/app/billing">Crediti e piani</a>
        </div>

        <form method="post" action="/studio/invite" style="margin-top:12px">
          <div class="studioInviteForm">
            <input class="input" name="winery_email" placeholder="Email cantina (es. cantina@...)" required>
            <select name="mode">
              <option value="both">Autorizza vista + modifica</option>
              <option value="view">Solo vista</option>
            </select>

            <select name="recommended_pack">
              <option value="" selected>Da valutare dopo registrazione</option>
              <option value="start">Suggerisci Start · 20 crediti · €29</option>
              <option value="pro">Suggerisci Cantina · 60 crediti · €79</option>
              <option value="plus">Suggerisci Business · 200 crediti · €199</option>
              <option value="unlimited">Suggerisci Non disponibile online</option>
            </select>

            <button class="btn btn-primary" type="submit">Invita una cantina</button>
          </div>
        </form>
        <div class="note" style="margin-top:12px">
          I nomi dei permessi restano invariati: la cantina si collega automaticamente usando il link ricevuto.
        </div>
      </div>

      <div class="studioSectionHead studioSectionTop">
        <div>
          <div class="studioKicker">Workspace</div>
          <div class="h2">Cantine collegate</div>
        </div>
        <div class="studioTotal">{len(wineries)} cantine · {total_labels} etichette</div>
      </div>

      <div class="studioClientGrid">
        {cards_html if cards_html else "<div class='card'><div class='p'>Nessuna cantina collegata.</div></div>"}
      </div>

      <div class="card" style="margin-top:14px">
        <div class="studioSectionHead">
          <div>
            <div class="studioKicker">Follow-up</div>
            <div class="h2">Ultimi inviti</div>
          </div>
          <a class="btn btn-primary" href="#studio-invite-form">Nuovo invito</a>
        </div>
        <div style="margin-top:12px;overflow:auto">
          <table class="studioInviteTable">
            <thead>
              <tr>
                <th>Link invito</th>
                <th>Email cantina</th>
                <th>Piano consigliato</th>
                <th>Creato</th>
                <th>Scadenza</th>
                <th>Stato</th>
                <th>Winery ID</th>
              </tr>
            </thead>
            <tbody>
              {inv_rows if inv_rows else "<tr><td colspan='7' class='muted'>Nessun invito.</td></tr>"}
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <style>
      .studioConsole {{ max-width:1180px; margin:0 auto; }}
      .studioHero {{
        margin-top:14px;
        display:grid;
        grid-template-columns:minmax(0,1fr) 430px;
        gap:24px;
        align-items:center;
        background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(248,252,250,.94));
        border:1px solid rgba(2,8,23,.08);
      }}
      .studioKicker {{ color:#0f766e; font-size:12px; font-weight:950; letter-spacing:.08em; text-transform:uppercase; margin-bottom:6px; }}
      .studioHeroActions, .studioInviteActions, .studioNextActions {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }}
      .studioHeroStats {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }}
      .studioHeroStats div, .studioClientMetrics div {{ border:1px solid rgba(2,8,23,.07); background:rgba(255,255,255,.76); border-radius:18px; padding:14px; }}
      .studioHeroStats span, .studioClientMetrics span, .studioMetricGrid span {{ display:block; color:#64748b; font-size:12px; font-weight:900; }}
      .studioHeroStats b {{ display:block; margin-top:5px; font-size:25px; line-height:1.05; font-weight:950; }}
      .studioGuide {{ margin-top:14px; padding:15px 18px; }}
      .studioGuide summary {{ cursor:pointer; font-weight:950; color:#0f172a; }}
      .studioGuideNote {{ margin-top:10px; background:rgba(248,250,252,.86); }}
      .studioSectionHead {{ display:flex; justify-content:space-between; gap:14px; align-items:center; flex-wrap:wrap; }}
      .studioSectionTop {{ margin-top:18px; }}
      .studioTotal {{ color:#64748b; font-size:13px; font-weight:900; }}
      .studioInviteForm {{ display:grid; grid-template-columns:minmax(220px,1fr) 240px 300px auto; gap:10px; align-items:end; }}
      .studioClientGrid {{ display:grid; gap:12px; margin-top:12px; }}
      .studioClientCard {{ padding:0; overflow:hidden; }}
      .studioClientMain {{ display:grid; grid-template-columns:minmax(280px,1fr) 440px auto; gap:16px; align-items:center; padding:16px; }}
      .studioClientIdentity {{ display:flex; gap:14px; align-items:center; min-width:0; }}
      .studioClientThumb {{ width:66px; height:66px; border-radius:16px; object-fit:cover; background:#eef2f7; border:1px solid var(--line); flex:0 0 auto; }}
      .studioClientKicker {{ color:#64748b; font-size:11px; font-weight:950; letter-spacing:.06em; text-transform:uppercase; }}
      .studioPerms {{ margin-top:7px; color:#64748b; font-size:12px; }}
      .studioClientMetrics {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; }}
      .studioClientMetrics b {{ display:block; margin-top:4px; font-size:22px; font-weight:950; }}
      .studioClientSide {{ display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; align-items:center; }}
      .studioInviteLinkBox input {{ width:100%; max-width:620px; font-size:12px; padding:10px 12px; border-radius:12px; font-family:monospace; }}
      .studioInviteTable th, .studioInviteTable td {{ vertical-align:top; }}
      @media(max-width:1050px) {{
        .studioHero, .studioClientMain, .studioInviteForm {{ grid-template-columns:1fr; }}
        .studioClientSide {{ justify-content:flex-start; }}
      }}
      @media(max-width:720px) {{
        .studioHeroStats, .studioClientMetrics {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
      }}
      @media(max-width:520px) {{
        .studioHeroStats, .studioClientMetrics {{ grid-template-columns:1fr; }}
        .studioHeroActions .btn, .studioInviteActions .btn, .studioInviteForm .btn {{ width:100%; }}
      }}
    </style>
    """

    return HTMLResponse(page(
        title="QRFACILE · Studio",
        subtitle="Area Studio",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=user.get("email", ""),
        role=user.get("role", ""),
        credits=None,
    ))


@router.post("/studio/invite")
def studio_invite(
    request: Request,
    winery_email: str = Form(...),
    mode: str = Form("both"),
    recommended_pack: str = Form(""),
):
    from qrfacile_app.csrf_core import require_csrf_or_same_origin
    require_csrf_or_same_origin(request)
    user = require_any_role(request, ("studio", "admin"))
    uid = int(user["id"])
    studio_email = (user.get("email") or "").strip().lower()

    winery_email = _clean_email(winery_email)
    mode = (mode or "both").strip().lower()
    recommended_pack = (recommended_pack or "").strip().lower()

    if recommended_pack not in ("", "start", "pro", "plus", "unlimited"):
        recommended_pack = ""

    if "@" not in winery_email or "." not in winery_email:
        return RedirectResponse("/studio?err=Email%20non%20valida", status_code=303)

    can_view = True
    can_edit = (mode == "both")
    can_create = (mode == "both")

    base_url = ""
    try:
        base_url = (getattr(request.app.state, "app_base_url", "") or "").rstrip("/")
    except Exception:
        base_url = ""

    if not base_url:
        host = request.headers.get("host", "")
        scheme = request.url.scheme
        if host:
            base_url = f"{scheme}://{host}".rstrip("/")

    from qrfacile_app.services.invitations import create_invitation
    invitation = create_invitation(invite_type="winery", inviter=user,
        recipient_email=winery_email, winery_id=None,
        permissions={"can_view":can_view,"can_edit":can_edit,"can_create":can_create})
    token = invitation.pop("raw_token")
    invite_path = f"/app/invite/winery/accept/{token}"
    invite_url = f"{base_url}{invite_path}" if base_url else invite_path

    pack_labels = {
        "start": "Start · 20 crediti · €29",
        "pro": "Cantina · 60 crediti · €79",
        "plus": "Business · 200 crediti · €199",
        "unlimited": "Non disponibile online",
    }
    recommended_label = pack_labels.get(recommended_pack, "-")

    sent, smtp_error = _send_winery_invite_email(
        to_email=winery_email,
        invite_link=invite_url,
        studio_email=studio_email or "uno studio grafico",
        recommended_pack_label=recommended_label,
    )

    if sent:
        msg = quote_plus("Invito creato ed email inviata alla cantina")
        return RedirectResponse(f"/studio?msg={msg}", status_code=303)

    msg = quote_plus("Invito creato. Email non inviata: copia il link dalla tabella e invialo manualmente")
    if smtp_error:
        err = quote_plus(f"SMTP: {smtp_error[:160]}")
        return RedirectResponse(f"/studio?msg={msg}&err={err}", status_code=303)

    return RedirectResponse(f"/studio?msg={msg}", status_code=303)


@router.post("/studio/winery/{winery_id}/recommended-pack")
def studio_winery_recommended_pack(
    request: Request,
    winery_id: int,
    recommended_pack: str = Form(""),
):
    user = require_any_role(request, ("studio", "admin"))
    uid = int(user["id"])
    role = (user.get("role") or "").lower().strip()

    recommended_pack = (recommended_pack or "").strip().lower()

    if recommended_pack not in ("", "start", "pro", "plus", "unlimited"):
        recommended_pack = ""

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if role == "admin":
                cur.execute("SELECT id FROM wineries WHERE id=%s LIMIT 1", (int(winery_id),))
                if not cur.fetchone():
                    return RedirectResponse("/studio?err=Cantina%20non%20trovata", status_code=303)

                return RedirectResponse(
                    f"/studio/winery/{int(winery_id)}?err=Il%20suggerimento%20piano%20va%20salvato%20dallo%20Studio%20collegato",
                    status_code=303,
                )

            perm = _studio_can_access_winery(cur, uid, int(winery_id))
            if not perm:
                return RedirectResponse("/studio?err=Accesso%20negato", status_code=303)

            cur.execute(
                """
                UPDATE studio_clients
                SET recommended_pack=%s
                WHERE studio_user_id=%s
                  AND winery_id=%s
                """,
                (recommended_pack or None, uid, int(winery_id)),
            )

            conn.commit()

    return RedirectResponse(
        f"/studio/winery/{int(winery_id)}?msg=Piano%20suggerito%20aggiornato",
        status_code=303,
    )


@router.get("/studio/winery/{winery_id}", response_class=HTMLResponse)
def studio_winery(request: Request, winery_id: int, msg: str = "", err: str = ""):
    user = require_any_role(request, ("studio", "admin"))
    uid = int(user["id"])
    role = (user.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if role == "admin":
                cur.execute("SELECT name FROM wineries WHERE id=%s LIMIT 1", (int(winery_id),))
                wr = cur.fetchone()
                if not wr:
                    raise HTTPException(404, "Cantina non trovata")
                perm = {"name": wr.get("name") or "Cantina", "can_view": True, "can_edit": True, "can_create": True}
            else:
                perm = _studio_can_access_winery(cur, uid, int(winery_id))
                if not perm:
                    return RedirectResponse("/studio?err=Accesso%20negato", status_code=303)

            if role == "admin":
                cur.execute(
                    """
                    SELECT
                      wl.id AS label_id,
                      wl.label_type,
                      wl.language,
                      wl.public_enabled,
                      qw.id AS wine_id,
                      qw.wine_name,
                      qw.lot,
                      qw.vintage
                    FROM wine_labels wl
                    JOIN qr_wines qw ON qw.id = wl.wine_id
                    WHERE wl.winery_id=%s
                    ORDER BY wl.id DESC
                    LIMIT 300
                    """,
                    (int(winery_id),),
                )
            else:
                cur.execute(
                    """
                    SELECT
                      wl.id AS label_id,
                      wl.label_type,
                      wl.language,
                      wl.public_enabled,
                      qw.id AS wine_id,
                      qw.wine_name,
                      qw.lot,
                      qw.vintage
                    FROM label_collaborators lc
                    JOIN wine_labels wl ON wl.id = lc.wine_label_id
                    JOIN qr_wines qw ON qw.id = wl.wine_id
                    WHERE lc.collaborator_user_id=%s
                      AND lc.active=TRUE
                      AND lc.can_view=TRUE
                      AND wl.winery_id=%s
                    ORDER BY wl.id DESC
                    LIMIT 300
                    """,
                    (uid, int(winery_id)),
                )
            labels = cur.fetchall() or []

    actions = top_actions(
        ("/studio", "← Studio"),
        ("/app/dashboard", "Dashboard"),
        ("/logout", "Logout"),
    )

    label_total = len(labels)
    label_public = len([l for l in labels if l.get("public_enabled")])
    label_draft = max(label_total - label_public, 0)

    label_cards = ""
    for l in labels:
        status_text = "Pubblica" if l.get("public_enabled") else "Bozza"
        status_tone = "green" if l.get("public_enabled") else "muted"
        label_cards += f"""
        <article class="card studioLabelCard">
          <div class="studioLabelMain">
            <div style="min-width:0;flex:1">
              <div class="studioKicker">Etichetta #{int(l['label_id'])}</div>
              <div class="h2">{esc(l.get("wine_name") or "Senza nome")}</div>
              <div class="studioLabelMeta">
                <span>Lotto <b>{esc(l.get("lot") or "-")}</b></span>
                {"<span>Annata <b>" + esc(l.get("vintage") or "") + "</b></span>" if l.get("vintage") else ""}
              </div>
              <div class="row" style="margin-top:10px;gap:8px;flex-wrap:wrap">
                {pill(l.get("label_type") or "-", "green")}
                {pill(l.get("language") or "-", "warn")}
                {pill(status_text, status_tone)}
              </div>
            </div>

            <div class="studioLabelActions">
              <a class="btn" href="/app/wine/{int(l['wine_id'])}?tab=images">Immagini</a>
              <a class="btn" href="/app/wine/{int(l['wine_id'])}?tab=export">Export QR</a>
              <a class="btn btn-primary" href="/app/label/{int(l['label_id'])}">Apri etichetta</a>
            </div>
          </div>
        </article>
        """

    pack_labels = {
        "": "Da valutare",
        "start": "Start · 20 crediti · €29",
        "pro": "Cantina · 60 crediti · €79",
        "plus": "Business · 200 crediti · €199",
        "unlimited": "Non disponibile online",
    }
    current_pack = (perm.get("recommended_pack") or "").strip().lower()
    if current_pack not in pack_labels:
        current_pack = ""

    def _sel_pack(v: str) -> str:
        return "selected" if current_pack == v else ""

    body = f"""
    <section class="studioWineryWorkspace">
      <div class="card studioWineryHero">
        <div>
          <div class="studioKicker">Workspace cantina</div>
          <div class="h1">{esc(perm.get('name') or 'Cantina')}</div>
          <div class="studioPerms mono">
            view={perm.get('can_view')} · edit={perm.get('can_edit')} · create={perm.get('can_create')}
          </div>
          <div class="studioHeroActions">
            <a class="btn btn-primary" href="#studio-labels">Apri etichette</a>
            <a class="btn" href="/app/dashboard">Dashboard lotti</a>
          </div>
        </div>

        <div class="studioMetricGrid">
          <div><span>Etichette assegnate</span><b>{label_total}</b></div>
          <div><span>Pubbliche</span><b>{label_public}</b></div>
          <div><span>Bozze</span><b>{label_draft}</b></div>
          <div><span>Piano</span><b>{esc(pack_labels.get(current_pack, "Da valutare"))}</b></div>
        </div>
      </div>

      <div class="card studioPlanCard">
        <div class="studioSectionHead">
          <div>
            <div class="studioKicker">Piano consigliato</div>
            <div class="h2">Suggerimento commerciale</div>
          </div>
          {pill(pack_labels.get(current_pack, "Da valutare"), "blue" if current_pack else "muted")}
        </div>

        <form method="post" action="/studio/winery/{int(winery_id)}/recommended-pack" style="margin-top:12px">
          <div class="studioPlanForm">
            <select name="recommended_pack">
              <option value="" {_sel_pack("")}>Da valutare</option>
              <option value="start" {_sel_pack("start")}>Start · 20 crediti · €29</option>
              <option value="pro" {_sel_pack("pro")}>Cantina · 60 crediti · €79</option>
              <option value="plus" {_sel_pack("plus")}>Business · 200 crediti · €199</option>
              <option value="unlimited" {_sel_pack("unlimited")}>Non disponibile online</option>
            </select>
            <button class="btn btn-primary" type="submit">Salva suggerimento</button>
          </div>
        </form>

        <details class="studioCompactNote">
          <summary>Note operative piano</summary>
          <div class="note" style="margin-top:10px;background:rgba(255,255,255,.72)">
            Il suggerimento è associato a questa cantina. I pacchetti legacy illimitati non sono proposti online.
          </div>
        </details>

        {paypal_checkout_form(
            request,
            pack="unlimited",
            billing_winery_id=int(winery_id),
            button_class="btn",
            disabled=True,
            disabled_label="Pacchetto legacy non acquistabile online",
            style="margin-top:12px",
        )}
        {paypal_checkout_script()}
      </div>

      <div class="studioSectionHead studioSectionTop" id="studio-labels">
        <div>
          <div class="studioKicker">Operatività</div>
          <div class="h2">Etichette assegnate</div>
        </div>
        <div class="studioTotal">{label_total} totali · {label_public} pubbliche</div>
      </div>

      <div class="studioLabelGrid">
        {label_cards if label_cards else "<div class='card'><div class='p'>Nessuna etichetta assegnata a questo studio per questa cantina.</div></div>"}
      </div>
    </section>

    <style>
      .studioWineryWorkspace {{ max-width:1180px; margin:0 auto; }}
      .studioWineryHero {{ margin-top:14px; display:grid; grid-template-columns:minmax(0,1fr) 430px; gap:24px; align-items:center; background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(248,252,250,.94)); border:1px solid rgba(2,8,23,.08); }}
      .studioKicker {{ color:#0f766e; font-size:12px; font-weight:950; letter-spacing:.08em; text-transform:uppercase; margin-bottom:6px; }}
      .studioPerms {{ margin-top:8px; color:#64748b; font-size:12px; }}
      .studioHeroActions {{ display:flex; gap:10px; flex-wrap:wrap; margin-top:16px; }}
      .studioMetricGrid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px; }}
      .studioMetricGrid div {{ border:1px solid rgba(2,8,23,.07); background:rgba(255,255,255,.76); border-radius:18px; padding:14px; }}
      .studioMetricGrid b {{ display:block; margin-top:5px; font-size:22px; line-height:1.08; font-weight:950; }}
      .studioSectionHead {{ display:flex; justify-content:space-between; gap:14px; align-items:center; flex-wrap:wrap; }}
      .studioSectionTop, .studioPlanCard, .studioLabelGrid {{ margin-top:14px; }}
      .studioTotal {{ color:#64748b; font-size:13px; font-weight:900; }}
      .studioPlanForm {{ display:flex; gap:10px; flex-wrap:wrap; align-items:end; }}
      .studioPlanForm select {{ max-width:360px; }}
      .studioCompactNote {{ margin-top:12px; }}
      .studioCompactNote summary {{ cursor:pointer; font-weight:900; color:#475569; }}
      .studioLabelGrid {{ display:grid; gap:12px; }}
      .studioLabelCard {{ padding:0; overflow:hidden; }}
      .studioLabelMain {{ display:flex; justify-content:space-between; gap:14px; align-items:center; flex-wrap:wrap; padding:16px; }}
      .studioLabelMeta {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; color:#64748b; font-size:13px; font-weight:800; }}
      .studioLabelMeta span {{ display:inline-flex; gap:4px; }}
      .studioLabelActions {{ display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }}
      @media(max-width:920px) {{ .studioWineryHero {{ grid-template-columns:1fr; }} .studioLabelActions {{ justify-content:flex-start; }} }}
      @media(max-width:560px) {{ .studioMetricGrid {{ grid-template-columns:1fr; }} .studioHeroActions .btn, .studioLabelActions .btn, .studioPlanForm .btn {{ width:100%; }} }}
    </style>
    """

    return HTMLResponse(page(
        title="QRFACILE · Studio · Cantina",
        subtitle="Cantina",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=user.get("email", ""),
        role=user.get("role", ""),
        credits=None,
    ))
