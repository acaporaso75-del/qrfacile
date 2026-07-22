from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, esc
from qrfacile_app.ui_layout import pill

router = APIRouter()

@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    user = require_any_role(request, ("admin",))
    uid = int(user["id"])

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            cur.execute("SELECT COUNT(*) FROM wineries")
            wineries = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) FROM studios")
            studios = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) FROM qr_wines")
            wines = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) FROM wine_labels")
            labels = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) FROM qr_items WHERE qr_type='external'")
            qr_links = cur.fetchone()["count"]

            cur.execute("""
                SELECT COALESCE(SUM(amount_cents),0)/100
                FROM credit_orders
                WHERE status='paid'
            """)
            revenue = cur.fetchone()["coalesce"]

    actions = top_actions(
        ("/app/start", "Menu"),
        ("/logout", "Logout"),
    )

    body = f"""
    <div class="card" style="margin-top:14px">
      <div class="h2">Statistiche Sistema</div>
      <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px">

        <div class="card">
          <b>Cantine</b>
          <div class="h2">{wineries}</div>
        </div>

        <div class="card">
          <b>Studi grafici</b>
          <div class="h2">{studios}</div>
        </div>

        <div class="card">
          <b>Lotti</b>
          <div class="h2">{wines}</div>
        </div>

        <div class="card">
          <b>Etichette</b>
          <div class="h2">{labels}</div>
        </div>

        <div class="card">
          <b>QR Link</b>
          <div class="h2">{qr_links}</div>
        </div>

        <div class="card">
          <b>Fatturato crediti (€)</b>
          <div class="h2">{revenue}</div>
        </div>

      </div>
    </div>
    """

    return HTMLResponse(page(
        title="QRFACILE · Admin",
        subtitle="Statistiche",
        body_html=body,
        actions_html=actions
    ))

