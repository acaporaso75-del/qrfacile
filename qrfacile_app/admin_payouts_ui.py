from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, esc
from qrfacile_app.ui_layout import pill

router = APIRouter()


def _is_admin(user: dict) -> bool:
    return (user.get("role") or "").lower().strip() == "admin"


def _balances(cur, user_id: int) -> dict:
    cur.execute(
        """
        SELECT credit_type, COALESCE(SUM(delta),0) AS bal
        FROM credit_ledger
        WHERE user_id=%s
        GROUP BY credit_type
        """,
        (int(user_id),),
    )
    out = {"wine": 0, "generic": 0}
    for r in (cur.fetchall() or []):
        ct = (r.get("credit_type") or "").strip().lower()
        if ct:
            out[ct] = int(r.get("bal") or 0)
    return out


def _pill_status(st: str) -> str:
    s = (st or "").lower()
    if s == "paid":
        return pill("PAID", "green")
    if s == "requested":
        return pill("REQUESTED", "warn")
    if s == "rejected":
        return pill("REJECTED", "muted")
    return pill(s.upper() or "—", "muted")


def _fmt_ts(v) -> str:
    if not v:
        return "-"
    try:
        return str(v)[:19]
    except Exception:
        return "-"


@router.get("/admin/payouts", response_class=HTMLResponse)
def admin_payouts(request: Request, status: str = "requested", msg: str = "", err: str = ""):
    user = require_any_role(request, ("admin", "studio", "winery"))
    if not _is_admin(user):
        raise HTTPException(403, "Forbidden")

    uid = int(user["id"])
    status = (status or "requested").strip().lower()
    if status not in ("requested", "paid", "rejected", "all"):
        status = "requested"

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            balances = _balances(cur, uid)

            if status == "all":
                cur.execute("""
                    SELECT pr.*, u.email AS studio_email
                    FROM payout_requests pr
                    JOIN users u ON u.id = pr.studio_user_id
                    ORDER BY pr.id DESC
                    LIMIT 300
                """)
            else:
                cur.execute("""
                    SELECT pr.*, u.email AS studio_email
                    FROM payout_requests pr
                    JOIN users u ON u.id = pr.studio_user_id
                    WHERE lower(pr.status)=lower(%s)
                    ORDER BY pr.id DESC
                    LIMIT 300
                """, (status,))
            rows = cur.fetchall() or []

    actions = (
        pill(f"wine: {balances.get('wine',0)}", "green")
        + " "
        + pill(f"generic: {balances.get('generic',0)}")
        + " "
        + top_actions(("/app/start", "Menu"), ("/app/dashboard", "Dashboard"), ("/logout", "Logout"))
    )

    filters = f"""
    <div class="card" style="margin-top:14px">
      <div class="row">
        <a class="pill" href="/admin/payouts?status=requested">Requested</a>
        <a class="pill" href="/admin/payouts?status=paid">Paid</a>
        <a class="pill" href="/admin/payouts?status=rejected">Rejected</a>
        <a class="pill" href="/admin/payouts?status=all">All</a>
      </div>
      <div class="note" style="margin-top:12px">
        Azione consigliata: verifica bonifico → inserisci CRO → <b>Segna pagato</b>.
      </div>
    </div>
    """

    table_rows = []
    for r in rows:
        pid = int(r["id"])
        st = (r.get("status") or "")
        studio_id = int(r["studio_user_id"])
        studio_email = r.get("studio_email") or "-"
        amount = float(r.get("amount_eur") or 0)
        iban = r.get("iban") or "-"
        beneficiary = r.get("beneficiary") or "-"
        requested_at = _fmt_ts(r.get("requested_at"))
        paid_at = _fmt_ts(r.get("paid_at"))
        admin_note = r.get("admin_note") or ""

        action_cell = "<span class='muted'>—</span>"
        if (st or "").lower() == "requested":
            action_cell = f"""
            <form method="post" action="/admin/payouts/{pid}/mark-paid" style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
              <input class="input" name="note" placeholder="CRO / riferimento bonifico" value="{esc(admin_note)}" style="max-width:320px">
              <button class="btn btn-primary" type="submit">Segna pagato</button>
            </form>
            <form method="post" action="/admin/payouts/{pid}/reject" style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap;align-items:center">
              <input class="input" name="note" placeholder="Motivo rifiuto" style="max-width:320px">
              <button class="btn" type="submit">Rifiuta</button>
            </form>
            """

        table_rows.append(f"""
        <tr>
          <td>{pid}</td>
          <td>{_pill_status(st)}</td>
          <td>
            <div><b>{studio_id}</b></div>
            <div class="muted">{esc(studio_email)}</div>
          </td>
          <td><b>{amount:.2f}€</b></td>
          <td>
            <div class="mono">{esc(iban)}</div>
            <div class="muted">{esc(beneficiary)}</div>
          </td>
          <td class="muted">{esc(requested_at)}</td>
          <td class="muted">{esc(paid_at)}</td>
          <td>{action_cell}</td>
        </tr>
        """)

    table_html = f"""
    <div class="card" style="margin-top:14px;overflow:auto">
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Stato</th>
            <th>Studio</th>
            <th>Importo</th>
            <th>IBAN / Beneficiario</th>
            <th>Richiesto</th>
            <th>Pagato</th>
            <th>Azioni</th>
          </tr>
        </thead>
        <tbody>
          {''.join(table_rows) if table_rows else "<tr><td colspan='8'><div class='note'>Nessuna richiesta</div></td></tr>"}
        </tbody>
      </table>
    </div>
    """

    body = f"""
    <div class="h1" style="margin-top:14px">Admin · Payout</div>
    <div class="p">Gestione payout studi (requested → paid/rejected). Accesso solo admin.</div>
    {filters}
    {table_html}
    """

    return HTMLResponse(page(
        title="QRFACILE · Admin Payout",
        subtitle="Admin · Payout",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
    ))


@router.post("/admin/payouts/{payout_id}/mark-paid")
def admin_mark_paid(request: Request, payout_id: int, note: str = Form("")):
    user = require_any_role(request, ("admin", "studio", "winery"))
    if not _is_admin(user):
        raise HTTPException(403, "Forbidden")

    note = (note or "").strip()[:200]

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM payout_requests WHERE id=%s LIMIT 1", (int(payout_id),))
            pr = cur.fetchone()
            if not pr or (pr.get("status") or "").lower() != "requested":
                return RedirectResponse("/admin/payouts?err=Stato%20non%20valido", status_code=303)

            studio_id = int(pr["studio_user_id"])

            cur.execute("""
                UPDATE payout_requests
                SET status='paid',
                    paid_at=NOW(),
                    decided_at=NOW(),
                    admin_note=%s
                WHERE id=%s
            """, (note, int(payout_id)))

            cur.execute("""
                UPDATE commission_ledger
                SET status='paid'
                WHERE studio_user_id=%s AND status='requested'
            """, (studio_id,))

            conn.commit()

    return RedirectResponse("/admin/payouts?msg=Payout%20segnato%20pagato", status_code=303)


@router.post("/admin/payouts/{payout_id}/reject")
def admin_reject(request: Request, payout_id: int, note: str = Form("")):
    user = require_any_role(request, ("admin", "studio", "winery"))
    if not _is_admin(user):
        raise HTTPException(403, "Forbidden")

    note = (note or "").strip()[:200]

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM payout_requests WHERE id=%s LIMIT 1", (int(payout_id),))
            pr = cur.fetchone()
            if not pr or (pr.get("status") or "").lower() != "requested":
                return RedirectResponse("/admin/payouts?err=Stato%20non%20valido", status_code=303)

            studio_id = int(pr["studio_user_id"])

            cur.execute("""
                UPDATE payout_requests
                SET status='rejected',
                    decided_at=NOW(),
                    admin_note=%s
                WHERE id=%s
            """, (note, int(payout_id)))

            cur.execute("""
                UPDATE commission_ledger
                SET status='available'
                WHERE studio_user_id=%s AND status='requested'
            """, (studio_id,))

            conn.commit()

    return RedirectResponse("/admin/payouts?msg=Payout%20rifiutato", status_code=303)
