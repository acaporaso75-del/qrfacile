from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import esc, page

router = APIRouter(tags=["invitation-center"])


def _winery_id(user: dict) -> int:
    with pg() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM wineries WHERE owner_user_id=%s LIMIT 1", (int(user["id"]),))
            row = cur.fetchone()
    if not row:
        raise HTTPException(403, "Cantina non trovata")
    return int(row[0])


def _status_label(item: dict) -> tuple[str, str]:
    status = str(item.get("status") or "pending")
    if status == "accepted":
        return "Accettato", "ok"
    if status == "revoked":
        return "Revocato", "off"
    if status == "expired":
        return "Scaduto", "warn"
    return "In attesa", "pending"


@router.get("/app/winery/invitations", response_class=HTMLResponse)
def winery_invitation_center(request: Request):
    # Compatibility URL: the canonical center includes sent and received invites.
    require_any_role(request, ("winery",))
    return RedirectResponse("/app/invitations", status_code=303)
    """Legacy renderer retained temporarily for source-history reference."""
    user = require_any_role(request, ("winery",))
    winery_id = _winery_id(user)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT token_hash, studio_email, status, email_delivery_status,
                       email_last_error, send_attempts, created_at, expires_at,
                       email_sent_at, accepted_at, revoked_at,
                       can_view, can_edit, can_create
                FROM studio_invites
                WHERE winery_id=%s
                ORDER BY created_at DESC
                LIMIT 100
                """,
                (winery_id,),
            )
            invites = [dict(row) for row in cur.fetchall()]

    cards = []
    for item in invites:
        label, tone = _status_label(item)
        delivery = str(item.get("email_delivery_status") or "not_sent")
        can_act = str(item.get("status") or "pending") == "pending"
        actions = ""
        if can_act:
            actions = f"""
            <div class='inviteActions'>
              <form method='post' action='/app/settings/studios/invites/{esc(item.get("token_hash") or "")}/resend'>
                <button class='btn' type='submit'>Reinvia email</button>
              </form>
              <form method='post' action='/app/settings/studios/invites/{esc(item.get("token_hash") or "")}/revoke' onsubmit="return confirm('Revocare questo invito?');">
                <button class='btn inviteDanger' type='submit'>Revoca</button>
              </form>
            </div>
            """
        error = item.get("email_last_error")
        error_html = f"<div class='inviteError'>{esc(str(error))}</div>" if error else ""
        permissions = []
        if item.get("can_view"):
            permissions.append("vista")
        if item.get("can_edit"):
            permissions.append("modifica")
        if item.get("can_create"):
            permissions.append("creazione")
        cards.append(f"""
        <article class='card inviteCard'>
          <div class='inviteTop'>
            <div>
              <div class='inviteKicker'>Studio invitato</div>
              <div class='h2'>{esc(item.get('studio_email') or '')}</div>
              <div class='p'>{esc(', '.join(permissions) or 'nessun permesso')}</div>
            </div>
            <span class='inviteStatus {tone}'>{esc(label)}</span>
          </div>
          <div class='inviteMetrics'>
            <div><span>Email</span><b>{esc(delivery)}</b></div>
            <div><span>Tentativi</span><b>{int(item.get('send_attempts') or 0)}</b></div>
            <div><span>Creato</span><b>{esc(str(item.get('created_at') or ''))}</b></div>
            <div><span>Scadenza</span><b>{esc(str(item.get('expires_at') or ''))}</b></div>
          </div>
          {error_html}
          {actions}
        </article>
        """)

    body = f"""
    <style>
      .inviteHero{{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;flex-wrap:wrap}}
      .inviteGrid{{display:grid;gap:12px;margin-top:14px}}
      .inviteCard{{display:grid;gap:14px}}
      .inviteTop{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}}
      .inviteKicker{{font-size:11px;text-transform:uppercase;letter-spacing:.07em;font-weight:950;color:#0f766e}}
      .inviteStatus{{padding:7px 10px;border-radius:999px;font-size:12px;font-weight:900;background:#e2e8f0}}
      .inviteStatus.ok{{background:#dcfce7;color:#166534}}.inviteStatus.warn{{background:#fef3c7;color:#92400e}}
      .inviteStatus.off{{background:#fee2e2;color:#991b1b}}.inviteStatus.pending{{background:#dbeafe;color:#1d4ed8}}
      .inviteMetrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}}
      .inviteMetrics div{{padding:12px;border:1px solid var(--border);border-radius:12px;background:rgba(248,250,252,.8)}}
      .inviteMetrics span{{display:block;font-size:11px;color:var(--muted);font-weight:900}}.inviteMetrics b{{display:block;margin-top:4px;font-size:13px}}
      .inviteActions{{display:flex;gap:8px;flex-wrap:wrap}}.inviteDanger{{color:#b91c1c;border-color:#fecaca}}
      .inviteError{{padding:10px;border-radius:10px;background:#fff7ed;color:#9a3412;font-size:12px}}
      @media(max-width:780px){{.inviteMetrics{{grid-template-columns:1fr 1fr}}}}
    </style>
    <div class='card inviteHero'>
      <div>
        <div class='inviteKicker'>Collaborazioni</div>
        <div class='h1'>Centro inviti</div>
        <div class='p'>Controlla chi è stato invitato, se l’email è partita e se l’invito è ancora valido.</div>
      </div>
      <div class='row'>
        <a class='btn btn-primary' href='/app/winery/settings#invite-studio'>Nuovo invito</a>
        <a class='btn' href='/app/winery/settings'>Studi autorizzati</a>
      </div>
    </div>
    <div class='inviteGrid'>{''.join(cards) if cards else "<div class='card'><div class='p'>Nessun invito registrato.</div></div>"}</div>
    """
    return HTMLResponse(page(request, user, "Centro inviti", body))
