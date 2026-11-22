"""Public abuse reports for module QR codes (/segnala/<slug>) and admin queue.

No login, no personal data stored about the reporter: only the reason and
an optional description. A honeypot field and a per-QR hourly cap keep bots
and floods out; unknown slugs are acknowledged without storing anything.
"""
from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import csrf_input, require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import esc, page, pill, top_actions

router = APIRouter()
MAX_REPORTS_PER_HOUR = 5
MAX_DETAILS = 1000
REASONS = {
    "scam": "Truffa o richiesta di soldi/dati",
    "malware": "Virus o sito pericoloso",
    "illegal": "Contenuto illegale o offensivo",
    "copyright": "Usa contenuti o marchi di altri",
    "other": "Altro",
}


def _public_page(body: str, status_code: int = 200) -> HTMLResponse:
    html = (
        "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'><title>Segnala contenuto · QRFacile</title>"
        "<link rel='stylesheet' href='/static/app.css'></head><body>"
        f"<main style='max-width:640px;margin:40px auto;padding:20px'><div class='card'>{body}</div></main></body></html>"
    )
    return HTMLResponse(html, status_code=status_code, headers={"Cache-Control": "no-store"})


def _thanks() -> HTMLResponse:
    return _public_page(
        "<h1 class='h1'>Grazie della segnalazione</h1>"
        "<p class='p'>La controlliamo il prima possibile. Se il contenuto viola le regole, il QR viene sospeso.</p>"
    )


@router.get("/segnala/{slug}", response_class=HTMLResponse)
def report_get(request: Request, slug: str):
    slug = (slug or "").strip()[:64]
    options = "".join(f'<option value="{k}">{esc(v)}</option>' for k, v in REASONS.items())
    return _public_page(f"""
      <h1 class="h1">Segnala un contenuto</h1>
      <p class="p">Il QR <code>{esc(slug)}</code> apre qualcosa di pericoloso, falso o illegale? Diccelo.
      Non chiediamo il tuo nome né la tua email.</p>
      <form method="post" action="/segnala/{esc(slug)}" style="display:grid;gap:12px">
        <div><label for="ab-reason">Motivo</label>
          <select id="ab-reason" name="reason" required>{options}</select></div>
        <div><label for="ab-details">Descrizione (facoltativa, massimo {MAX_DETAILS} caratteri)</label>
          <textarea id="ab-details" class="input" name="details" rows="4" maxlength="{MAX_DETAILS}"></textarea></div>
        <div aria-hidden="true" style="position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden">
          <label for="ab-website">Non compilare</label>
          <input id="ab-website" name="website" tabindex="-1" autocomplete="off">
        </div>
        <button class="btn btn-primary" type="submit">Invia segnalazione</button>
      </form>
    """)


@router.post("/segnala/{slug}")
def report_post(
    request: Request,
    slug: str,
    reason: str = Form(""),
    details: str = Form(""),
    website: str = Form(""),
):
    if reason not in REASONS:
        raise HTTPException(422, "Motivo non valido")
    if (website or "").strip():
        return _thanks()
    slug = (slug or "").strip()[:64]
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT id FROM qr_items q
                   WHERE slug=%s AND (to_jsonb(q)->>'module'='link' OR qr_type='external') LIMIT 1""",
                (slug,),
            )
            row = cur.fetchone()
            if not row:
                return _thanks()
            qr_id = int(row["id"])
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('abuse-report'), %s)", (qr_id,))
            cur.execute(
                "SELECT COUNT(*) AS n FROM abuse_reports WHERE qr_item_id=%s AND created_at > now() - interval '1 hour'",
                (qr_id,),
            )
            if int((cur.fetchone() or {}).get("n") or 0) >= MAX_REPORTS_PER_HOUR:
                return _thanks()
            cur.execute(
                "INSERT INTO abuse_reports (qr_item_id, reason, details) VALUES (%s, %s, %s)",
                (qr_id, reason, " ".join((details or "").split())[:MAX_DETAILS] or None),
            )
        conn.commit()
    return _thanks()


@router.get("/admin/abuse-reports", response_class=HTMLResponse)
def admin_reports(request: Request, msg: str = "", err: str = ""):
    user = require_any_role(request, ("admin",))
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT r.id, r.reason, r.details, r.created_at, q.id AS qr_id, q.slug, q.title, q.status,
                       q.payload->>'type' AS kind, u.email AS owner_email
                FROM abuse_reports r
                LEFT JOIN qr_items q ON q.id = r.qr_item_id
                LEFT JOIN users u ON u.id = q.owner_user_id
                WHERE r.handled_at IS NULL
                ORDER BY r.created_at DESC
                LIMIT 200
                """
            )
            rows = cur.fetchall() or []
    token = csrf_input(request)
    cards = []
    for row in rows:
        active = (row.get("status") or "").lower() == "attiva"
        unpublish = (
            f"""<form method="post" action="/admin/abuse-reports/{int(row['id'])}/handled" style="display:inline">
              {token}<input type="hidden" name="unpublish" value="on">
              <button class="btn btn-danger-soft" type="submit">Sospendi il QR e chiudi</button></form>"""
            if active else ""
        )
        cards.append(f"""
        <article class="card" style="margin-top:12px">
          <div class="row" style="justify-content:space-between;gap:8px;flex-wrap:wrap">
            <strong>{esc(REASONS.get(row.get('reason') or '', row.get('reason') or ''))}</strong>
            {pill('QR attivo', 'warn') if active else pill('QR non attivo', 'muted')}
          </div>
          <p class="p">QR <a href="/d/{esc(row.get('slug') or '')}" rel="noopener" target="_blank">{esc(row.get('slug') or '-')}</a>
            · {esc(row.get('title') or '-')} · {esc(row.get('kind') or 'link')} · {esc(row.get('owner_email') or '-')}</p>
          <p class="p">{esc(row.get('details') or 'Nessuna descrizione')}</p>
          <p class="muted">{esc(str(row.get('created_at') or ''))}</p>
          <div class="row" style="gap:8px">
            {unpublish}
            <form method="post" action="/admin/abuse-reports/{int(row['id'])}/handled" style="display:inline">
              {token}<button class="btn" type="submit">Segna come gestita</button></form>
          </div>
        </article>
        """)
    body = "".join(cards) or "<div class='card'><p>Nessuna segnalazione aperta.</p></div>"
    return HTMLResponse(page(
        title="QRFACILE · Segnalazioni",
        subtitle="Contenuti segnalati dei QR Link",
        body_html=body,
        actions_html=top_actions(("/admin", "Admin"), ("/admin/modules", "Moduli")),
        msg=msg,
        err=err,
        role="admin",
        user_email=user.get("email", ""),
        credits=None,
    ))


@router.post("/admin/abuse-reports/{report_id}/handled")
def admin_handle(request: Request, report_id: int, unpublish: str = Form("")):
    require_csrf_or_same_origin(request)
    user = require_any_role(request, ("admin",))
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "UPDATE abuse_reports SET handled_at=now(), handled_by=%s WHERE id=%s AND handled_at IS NULL RETURNING qr_item_id",
                (int(user["id"]), int(report_id)),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Segnalazione non trovata o già gestita")
            if unpublish == "on" and row.get("qr_item_id"):
                cur.execute("UPDATE qr_items SET status='bozza' WHERE id=%s", (int(row["qr_item_id"]),))
                if _has_audit_log(cur):
                    cur.execute(
                        """
                        INSERT INTO audit_log (user_id, role, action, entity_type, entity_id, ip, user_agent, meta, created_at)
                        VALUES (%s, 'admin', 'abuse_qr_suspended', 'qr_items', %s, NULL, 'admin-abuse-reports',
                                jsonb_build_object('report_id', %s::bigint), now())
                        """,
                        (int(user["id"]), int(row["qr_item_id"]), int(report_id)),
                    )
        conn.commit()
    message = "QR sospeso e segnalazione chiusa" if unpublish == "on" else "Segnalazione chiusa"
    return RedirectResponse(f"/admin/abuse-reports?msg={message.replace(' ', '%20')}", status_code=303)


def _has_audit_log(cur) -> bool:
    cur.execute("SELECT to_regclass('audit_log') AS t")
    row = cur.fetchone() or {}
    return bool(row.get("t"))
