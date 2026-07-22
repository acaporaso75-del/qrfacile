import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, esc, pill

router = APIRouter()


def _fmt_ts(ts) -> str:
    if not ts:
        return "-"
    try:
        return time.strftime("%d/%m/%Y %H:%M", time.localtime(int(ts)))
    except Exception:
        return str(ts)[:19]


def _money(cents, currency="EUR") -> str:
    try:
        return f"{int(cents or 0) / 100:.2f} {currency}".replace(".", ",")
    except Exception:
        return "-"


def _simple_table(rows, headers=None, empty="Nessun dato disponibile") -> str:
    if not rows:
        return f"<div class='p' style='margin-top:10px'>{esc(empty)}</div>"

    if headers is None:
        headers = list(rows[0].keys())

    thead = "".join(f"<th>{esc(str(h))}</th>" for h in headers)
    tbody = ""

    for r in rows:
        tbody += "<tr>"
        for h in headers:
            v = r.get(h, "-")
            if v is None:
                v = "-"
            tbody += f"<td>{esc(str(v))}</td>"
        tbody += "</tr>"

    return f"""
    <div style="overflow:auto;margin-top:12px">
      <table>
        <thead><tr>{thead}</tr></thead>
        <tbody>{tbody}</tbody>
      </table>
    </div>
    """


def _balances(cur, user_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT credit_type, COALESCE(SUM(delta),0) AS saldo
        FROM credit_ledger
        WHERE user_id=%s
        GROUP BY credit_type
        ORDER BY credit_type
        """,
        (int(user_id),),
    )
    return cur.fetchall() or []


@router.get("/admin/customer/{winery_id}", response_class=HTMLResponse)
def admin_customer(request: Request, winery_id: int, msg: str = "", err: str = ""):
    user = require_any_role(request, ("admin",))
    winery_id = int(winery_id)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                  w.*,
                  u.id AS owner_user_id_real,
                  u.email AS owner_email,
                  u.role AS owner_role,
                  u.created_at AS owner_created_at
                FROM wineries w
                JOIN users u ON u.id = w.owner_user_id
                WHERE w.id=%s
                LIMIT 1
                """,
                (winery_id,),
            )
            winery = cur.fetchone()

            if not winery:
                body = """
                <div class="card" style="margin-top:14px">
                  <div class="h1">Cantina non trovata</div>
                  <div class="p">La cantina richiesta non esiste.</div>
                </div>
                """
                return HTMLResponse(page(
                    title="QRFACILE · Scheda cliente",
                    subtitle="Admin cliente",
                    body_html=body,
                    actions_html=top_actions(("/admin", "Admin")),
                    role="admin",
                    user_email=user.get("email", ""),
                    msg=msg,
                    err=err,
                ), status_code=404)

            owner_user_id = int(winery["owner_user_id"])

            credits = _balances(cur, owner_user_id)

            cur.execute(
                """
                SELECT id, plan, status, starts_at, expires_at, source_order_id
                FROM subscriptions
                WHERE user_id=%s
                   OR winery_id=%s
                ORDER BY expires_at DESC NULLS LAST, id DESC
                LIMIT 50
                """,
                (owner_user_id, winery_id),
            )
            subs_raw = cur.fetchall() or []
            subs = []
            for s in subs_raw:
                subs.append({
                    "ID": s.get("id"),
                    "Piano": s.get("plan"),
                    "Stato": s.get("status"),
                    "Inizio": _fmt_ts(s.get("starts_at")),
                    "Scadenza": _fmt_ts(s.get("expires_at")),
                    "Ordine": s.get("source_order_id") or "-",
                })

            cur.execute(
                """
                SELECT id, pack, amount_cents, currency, status, billing_winery_id,
                       created_at, paid_at, paypal_order_id, paypal_capture_id
                FROM orders
                WHERE user_id=%s
                   OR billing_winery_id=%s
                ORDER BY id DESC
                LIMIT 100
                """,
                (owner_user_id, winery_id),
            )
            orders_raw = cur.fetchall() or []
            orders = []
            for o in orders_raw:
                orders.append({
                    "ID": o.get("id"),
                    "Pack": o.get("pack"),
                    "Importo": _money(o.get("amount_cents"), o.get("currency") or "EUR"),
                    "Stato": o.get("status"),
                    "Cantina": o.get("billing_winery_id") or "-",
                    "Creato": _fmt_ts(o.get("created_at")),
                    "Pagato": _fmt_ts(o.get("paid_at")),
                })

            cur.execute(
                """
                SELECT
                  sc.studio_user_id,
                  su.email AS studio_email,
                  COALESCE(st.company_name, '') AS studio_name,
                  sc.can_view,
                  sc.can_edit,
                  sc.can_create,
                  COALESCE(sc.recommended_pack, '') AS recommended_pack,
                  sc.created_at
                FROM studio_clients sc
                JOIN users su ON su.id = sc.studio_user_id
                LEFT JOIN studios st ON st.user_id = sc.studio_user_id
                WHERE sc.winery_id=%s
                ORDER BY sc.created_at DESC
                """,
                (winery_id,),
            )
            studios_raw = cur.fetchall() or []
            studios = []
            for st in studios_raw:
                studios.append({
                    "Studio": st.get("studio_name") or "-",
                    "Email": st.get("studio_email"),
                    "View": st.get("can_view"),
                    "Edit": st.get("can_edit"),
                    "Create": st.get("can_create"),
                    "Piano suggerito": st.get("recommended_pack") or "-",
                    "Collegato": _fmt_ts(st.get("created_at")),
                })

            cur.execute(
                """
                SELECT token, studio_email, recommended_pack, created_at, expires_at, used_at, used_by_user_id
                FROM studio_invites
                WHERE winery_id=%s
                   OR used_by_user_id=%s
                ORDER BY created_at DESC
                LIMIT 50
                """,
                (winery_id, owner_user_id),
            )
            invites_raw = cur.fetchall() or []
            invites = []
            for i in invites_raw:
                invites.append({
                    "Email invitata": i.get("studio_email") or "-",
                    "Piano": i.get("recommended_pack") or "-",
                    "Creato": _fmt_ts(i.get("created_at")),
                    "Scade": _fmt_ts(i.get("expires_at")),
                    "Usato": _fmt_ts(i.get("used_at")),
                })

            cur.execute(
                """
                SELECT qw.id, qw.wine_name, qw.vintage, qw.lot,
                       COALESCE(qi.status, '') AS status,
                       qi.slug, qw.created_at
                FROM qr_wines qw
                LEFT JOIN qr_items qi ON qi.id = qw.qr_item_id
                WHERE qw.winery_id=%s
                ORDER BY qw.id DESC
                LIMIT 200
                """,
                (winery_id,),
            )
            wines_raw = cur.fetchall() or []
            wines = []
            for w in wines_raw:
                wines.append({
                    "ID": w.get("id"),
                    "Vino": w.get("wine_name") or "-",
                    "Annata": w.get("vintage") or "-",
                    "Lotto": w.get("lot") or "-",
                    "Stato": w.get("status") or "-",
                    "Slug": w.get("slug") or "-",
                    "Creato": _fmt_ts(w.get("created_at")),
                })

            # Tabelle assistenza: se non esistono ancora, non mandiamo in errore la scheda.
            entitlements = []
            usage = []
            try:
                cur.execute(
                    """
                    SELECT id, service_code, service_name, allowance_units, used_units,
                           status, starts_at, expires_at, source_order_id
                    FROM service_entitlements
                    WHERE user_id=%s
                       OR winery_id=%s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 100
                    """,
                    (owner_user_id, winery_id),
                )
                ent_raw = cur.fetchall() or []
                ent_ids = []
                for e in ent_raw:
                    eid = int(e.get("id"))
                    ent_ids.append(eid)
                    total = int(e.get("allowance_units") or 0)
                    used = int(e.get("used_units") or 0)
                    entitlements.append({
                        "ID": eid,
                        "Servizio": e.get("service_name"),
                        "Totale": total,
                        "Usato": used,
                        "Residuo": max(0, total - used),
                        "Stato": e.get("status"),
                        "Inizio": _fmt_ts(e.get("starts_at")),
                        "Scadenza": _fmt_ts(e.get("expires_at")),
                        "Ordine": e.get("source_order_id") or "-",
                    })

                if ent_ids:
                    cur.execute(
                        """
                        SELECT sul.id, sul.entitlement_id, sul.units, sul.activity_type,
                               sul.note, sul.created_at, au.email AS admin_email
                        FROM service_usage_ledger sul
                        LEFT JOIN users au ON au.id = sul.admin_user_id
                        WHERE sul.entitlement_id = ANY(%s)
                        ORDER BY sul.created_at DESC, sul.id DESC
                        LIMIT 300
                        """,
                        (ent_ids,),
                    )
                    usage_raw = cur.fetchall() or []
                    for u in usage_raw:
                        usage.append({
                            "ID": u.get("id"),
                            "Servizio ID": u.get("entitlement_id"),
                            "Unità": u.get("units"),
                            "Attività": u.get("activity_type"),
                            "Nota": u.get("note") or "-",
                            "Admin": u.get("admin_email") or "-",
                            "Data": _fmt_ts(u.get("created_at")),
                        })
            except Exception:
                conn.rollback()
                entitlements = []
                usage = []

    winery_fields = []
    skip = {"owner_user_id_real", "owner_email", "owner_role", "owner_created_at"}
    for k, v in dict(winery).items():
        if k in skip:
            continue
        winery_fields.append({
            "Campo": k,
            "Valore": v if v is not None else "-",
        })

    actions = top_actions(
        ("/admin", "Admin"),
        ("/app/dashboard", "Dashboard"),
        ("/admin/credits", "Crediti"),
        ("/logout", "Logout"),
    )

    body = f"""
    <section style="max-width:1180px;margin:0 auto">
      <div class="card" style="margin-top:14px;background:linear-gradient(135deg,rgba(236,253,245,.88),rgba(239,246,255,.88));border:1px solid rgba(2,8,23,.08)">
        <div class="h1">Scheda cliente</div>
        <div class="p" style="margin-top:8px;line-height:1.6">
          Vista completa della cantina: dati, piani, pagamenti, crediti, assistenza, lavori, studio e QR.
        </div>

        <div class="row" style="margin-top:14px;gap:8px;flex-wrap:wrap">
          {pill(f"Cantina #{winery_id}", "green")}
          {pill(f"Utente #{owner_user_id}", "muted")}
          {pill(str(winery.get("owner_email") or "-"), "blue")}
        </div>

        <div class="row" style="margin-top:14px;gap:10px;flex-wrap:wrap">
          <a class="btn btn-primary" href="/admin">Torna ad Admin</a>
          <form method="post" action="/app/set-winery" style="display:inline">
            <input type="hidden" name="winery_id" value="{winery_id}">
            <input type="hidden" name="next_url" value="/admin/customer/{winery_id}">
            <button class="btn" type="submit">Imposta contesto</button>
          </form>
        </div>
      </div>

      <div class="card" style="margin-top:14px">
        <div class="h2">{esc(winery.get("name") or "Cantina")}</div>
        <div class="p" style="margin-top:8px">
          Account proprietario: <b>{esc(winery.get("owner_email") or "-")}</b><br>
          Creato: <b>{esc(_fmt_ts(winery.get("owner_created_at")))}</b>
        </div>
      </div>

      <div class="card" style="margin-top:14px">
        <div class="h2">Dati cantina</div>
        {_simple_table(winery_fields, empty="Nessun dato cantina")}
      </div>

      <div class="card" style="margin-top:14px">
        <div class="h2">Crediti disponibili</div>
        {_simple_table(credits, empty="Nessun credito")}
      </div>

      <div class="card" style="margin-top:14px">
        <div class="h2">Piani QR</div>
        {_simple_table(subs, empty="Nessun piano QR")}
      </div>

      <div class="card" style="margin-top:14px">
        <div class="h2">Ordini e pagamenti</div>
        {_simple_table(orders, empty="Nessun ordine")}
      </div>

      <div class="card" style="margin-top:14px">
        <div class="h2">Assistenza QRFACILE acquistata</div>
        {_simple_table(entitlements, empty="Nessuna assistenza acquistata")}
      </div>

      <div class="card" style="margin-top:14px">
        <div class="h2">Lavori scalati</div>
        {_simple_table(usage, empty="Nessun lavoro scalato")}
      </div>

      <div class="card" style="margin-top:14px">
        <div class="h2">Studio grafico collegato</div>
        {_simple_table(studios, empty="Nessuno studio collegato")}
      </div>

      <div class="card" style="margin-top:14px">
        <div class="h2">Inviti</div>
        {_simple_table(invites, empty="Nessun invito")}
      </div>

      <div class="card" style="margin-top:14px">
        <div class="h2">QR e lotti vino</div>
        {_simple_table(wines, empty="Nessun lotto vino")}
      </div>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Scheda cliente",
        subtitle="Admin cliente",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=user.get("email", ""),
        role="admin",
        credits=None,
    ))
