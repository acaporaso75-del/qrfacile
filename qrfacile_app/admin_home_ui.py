import time
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, esc

router = APIRouter()


def _now_epoch() -> int:
    return int(time.time())


def _get_active_winery_id(cur, user_id: int) -> int | None:
    cur.execute("SELECT admin_active_winery_id FROM users WHERE id=%s LIMIT 1", (int(user_id),))
    r = cur.fetchone() or {}
    wid = r.get("admin_active_winery_id")
    return int(wid) if wid else None


def _set_active_winery_id(cur, user_id: int, winery_id: int | None) -> None:
    cur.execute(
        "UPDATE users SET admin_active_winery_id=%s WHERE id=%s",
        (int(winery_id) if winery_id else None, int(user_id)),
    )


def _relation_columns(cur, table: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    return {str(row["column_name"]) for row in (cur.fetchall() or [])}


def _load_revenue_kpi(cur, out: dict) -> None:
    order_columns = _relation_columns(cur, "orders")
    required = {"amount_cents", "status", "payment_environment"}
    out["orders_revenue_available"] = required <= order_columns
    if out["orders_revenue_available"]:
        cur.execute(
            """
            SELECT
              COALESCE(SUM(amount_cents) FILTER (
                WHERE status='paid' AND payment_environment='live'
              ), 0) AS live_cents,
              COALESCE(SUM(amount_cents) FILTER (
                WHERE status='paid' AND payment_environment='sandbox'
              ), 0) AS sandbox_cents,
              COALESCE(SUM(amount_cents) FILTER (
                WHERE status='paid' AND payment_environment='manual'
              ), 0) AS manual_cents,
              COALESCE(SUM(amount_cents) FILTER (
                WHERE status='paid' AND payment_environment='unknown'
              ), 0) AS unknown_cents
            FROM orders
            """
        )
        totals = cur.fetchone() or {}
        for key in ("live", "sandbox", "manual", "unknown"):
            out[f"revenue_{key}_eur"] = float(totals.get(f"{key}_cents") or 0) / 100.0

    legacy_columns = _relation_columns(cur, "credit_orders")
    out["legacy_revenue_available"] = {"amount_cents", "status"} <= legacy_columns
    if out["legacy_revenue_available"]:
        cur.execute("SELECT COALESCE(SUM(amount_cents),0) AS s FROM credit_orders WHERE status='paid'")
        out["revenue_legacy_eur"] = float((cur.fetchone() or {}).get("s") or 0) / 100.0


def _kpi(cur) -> dict:
    out = {}

    cur.execute("SELECT COUNT(*) AS n FROM wineries")
    out["wineries"] = int((cur.fetchone() or {}).get("n") or 0)

    cur.execute("SELECT COUNT(*) AS n FROM users WHERE lower(role)='studio'")
    out["studios"] = int((cur.fetchone() or {}).get("n") or 0)

    cur.execute("SELECT COUNT(*) AS n FROM qr_wines")
    out["lots"] = int((cur.fetchone() or {}).get("n") or 0)

    cur.execute("SELECT COUNT(*) AS n FROM wine_labels")
    out["labels"] = int((cur.fetchone() or {}).get("n") or 0)

    cur.execute("SELECT COUNT(*) AS n FROM qr_items WHERE qr_type='external'")
    out["external_qr"] = int((cur.fetchone() or {}).get("n") or 0)

    _load_revenue_kpi(cur, out)

    since = _now_epoch() - (30 * 24 * 3600)

    cur.execute("SELECT COUNT(*) AS n FROM wineries WHERE created_at >= %s", (since,))
    out["wineries_30d"] = int((cur.fetchone() or {}).get("n") or 0)

    cur.execute("SELECT COUNT(*) AS n FROM qr_wines WHERE created_at >= %s", (since,))
    out["lots_30d"] = int((cur.fetchone() or {}).get("n") or 0)

    cur.execute("SELECT COUNT(*) AS n FROM wine_labels WHERE created_at >= %s", (since,))
    out["labels_30d"] = int((cur.fetchone() or {}).get("n") or 0)

    return out


def _active_winery_card(cur, winery_id: int) -> str:
    cur.execute(
        """
        SELECT id, name
        FROM wineries
        WHERE id=%s
        LIMIT 1
        """,
        (int(winery_id),),
    )
    w = cur.fetchone()
    if not w:
        return ""

    wid = int(w["id"])
    name = esc(w.get("name") or "")

    cur.execute("SELECT COUNT(*) AS n FROM qr_wines WHERE winery_id=%s", (wid,))
    lots = int((cur.fetchone() or {}).get("n") or 0)

    cur.execute("SELECT COUNT(*) AS n FROM wine_labels WHERE winery_id=%s", (wid,))
    labels = int((cur.fetchone() or {}).get("n") or 0)

    return f"""
    <div class="card" style="margin-top:14px;border-left:4px solid rgba(34,197,94,.55)">
      <div class="h2">Contesto attivo</div>
      <div class="p"><b>{name}</b> (ID {wid})</div>
      <div class="note" style="margin-top:10px">
        Lotti: <b>{lots}</b> · Etichette: <b>{labels}</b>
      </div>
      <div class="row" style="margin-top:12px">
        <a class="btn btn-primary" href="/app/dashboard">Apri Dashboard filtrata</a>
        <a class="btn" href="/admin/customer/{wid}">Scheda cliente</a>
        <a class="btn" href="/app/labels/search">Apri Ricerca etichette filtrata</a>

        <form method="post" action="/app/clear-winery" style="display:inline">
          <input type="hidden" name="next_url" value="/admin">
          <button class="btn" type="submit">Reset contesto</button>
        </form>
      </div>
    </div>
    """


@router.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, q: str = "", msg: str = "", err: str = ""):
    u = require_any_role(request, ("admin",))
    uid = int(u["id"])
    q = (q or "").strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            active_winery_id = _get_active_winery_id(cur, uid)
            kpi = _kpi(cur)

            wineries = []
            if q:
                like = f"%{q.lower()}%"
                cur.execute(
                    """
                    SELECT id, name
                    FROM wineries
                    WHERE lower(name) LIKE %s OR CAST(id AS text) LIKE %s
                    ORDER BY lower(name)
                    LIMIT 50
                    """,
                    (like, like),
                )
                wineries = cur.fetchall() or []

            active_card = _active_winery_card(cur, active_winery_id) if active_winery_id else ""

    actions = top_actions(
        ("/app/start", "Menu"),
        ("/app/dashboard", "Dashboard"),
        ("/admin/paypal-webhooks", "Eventi PayPal"),
        ("/logout", "Logout"),
    )

    if kpi["orders_revenue_available"]:
        order_revenue_html = f"""
          <div class="p"><b>{kpi['revenue_live_eur']:.2f}€</b></div>
          <div class="muted" style="font-size:12px;margin-top:6px">
            Sandbox: {kpi['revenue_sandbox_eur']:.2f}€ ·
            Manuale: {kpi['revenue_manual_eur']:.2f}€ ·
            Storico non classificato: {kpi['revenue_unknown_eur']:.2f}€
          </div>
        """
    else:
        order_revenue_html = """
          <div class="note note-warn"><b>Non disponibile</b>: migrazione ambiente pagamenti non applicata.</div>
        """
    legacy_revenue_html = (
        f"<div class='muted' style='font-size:12px;margin-top:6px'>Legacy credit_orders: {kpi['revenue_legacy_eur']:.2f}€</div>"
        if kpi["legacy_revenue_available"]
        else "<div class='muted' style='font-size:12px;margin-top:6px'>Legacy credit_orders: non disponibile</div>"
    )

    kpi_html = f"""
    <div class="card" style="margin-top:14px">
      <div class="h2">Statistiche piattaforma</div>
      <div class="grid2" style="margin-top:12px">
        <div class="card">
          <div class="h2">Cantine</div>
          <div class="p"><b>{kpi['wineries']}</b> tot · <b>{kpi['wineries_30d']}</b> ultimi 30gg</div>
        </div>
        <div class="card">
          <div class="h2">Studi</div>
          <div class="p"><b>{kpi['studios']}</b> tot</div>
        </div>
        <div class="card">
          <div class="h2">Lotti</div>
          <div class="p"><b>{kpi['lots']}</b> tot · <b>{kpi['lots_30d']}</b> ultimi 30gg</div>
        </div>
        <div class="card">
          <div class="h2">Etichette</div>
          <div class="p"><b>{kpi['labels']}</b> tot · <b>{kpi['labels_30d']}</b> ultimi 30gg</div>
        </div>
        <div class="card">
          <div class="h2">QR Link</div>
          <div class="p"><b>{kpi['external_qr']}</b> creati</div>
        </div>
        <div class="card">
          <div class="h2">Incassi Live verificati</div>
          {order_revenue_html}
          {legacy_revenue_html}
        </div>
      </div>
    </div>
    """

    res_html = ""
    if q:
        if not wineries:
            res_html = f"""
            <div class="card" style="margin-top:14px">
              <div class="h2">Risultati ricerca</div>
              <div class="p">Nessuna cantina trovata per: <b>{esc(q)}</b></div>
            </div>
            """
        else:
            rows = []
            for w in wineries:
                wid = int(w["id"])
                name = esc(w.get("name") or "")
                rows.append(f"""
                <tr>
                  <td><b>{name}</b><div class="muted" style="font-size:12px">ID {wid}</div></td>
                  <td style="white-space:nowrap">
                    <div class="row" style="gap:8px;flex-wrap:wrap">
                      <form method="post" action="/app/set-winery" style="display:inline">
                        <input type="hidden" name="winery_id" value="{wid}">
                        <input type="hidden" name="next_url" value="/admin">
                        <button class="btn btn-primary" type="submit">Imposta contesto</button>
                      </form>
                      <a class="btn" href="/admin/customer/{wid}">Scheda cliente</a>
                    </div>
                  </td>
                </tr>
                """)
            res_html = f"""
            <div class="card" style="margin-top:14px">
              <div class="h2">Risultati ricerca</div>
              <div style="margin-top:12px;overflow:auto">
                <table>
                  <thead><tr><th>Cantina</th><th></th></tr></thead>
                  <tbody>{''.join(rows)}</tbody>
                </table>
              </div>
            </div>
            """

    search_html = f"""
    <div class="card" style="margin-top:14px">
      <div class="h2">Seleziona una cantina</div>
      <div class="p">
        Cerca una cantina per impostare il contesto. Così dashboard e ricerca etichette lavoreranno
        su una sola cantina per volta.
      </div>

      <form method="get" action="/admin" style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap">
        <input class="input" name="q" value="{esc(q)}" placeholder="Cerca cantina per nome o ID..." style="min-width:320px">
        <button class="btn btn-primary" type="submit">Cerca</button>
        <a class="btn" href="/admin">Reset</a>
      </form>
    </div>
    """

    body = f"""
    <div class="h1" style="margin-top:14px">Admin Console</div>
    <div class="p">Controllo sistema · statistiche · contesto cantina.</div>

    {kpi_html}
    {active_card}
    {search_html}
    {res_html}
    """

    return HTMLResponse(page(
        title="QRFACILE · Admin",
        subtitle="Admin",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=u.get("email", ""),
        role="admin",
        credits=None,
    ))


@router.post("/admin/set-winery")
def admin_set_winery(request: Request, winery_id: str = Form("")):
    require_csrf_or_same_origin(request)
    """
    Compat legacy: manteniamo questa route, ma reindirizziamo alla logica nuova.
    """
    wid = (winery_id or "").strip()
    if wid:
        return RedirectResponse(f"/admin?q=&msg=Usa%20il%20nuovo%20selettore", status_code=303)
    return RedirectResponse("/admin", status_code=303)
