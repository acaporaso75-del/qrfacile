import time

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, pill, esc
from qrfacile_app.pricing_config import get_purchase_pack, list_billing_packs

router = APIRouter()


def now() -> int:
    return int(time.time())


def _cleanup_old_pending_orders(cur, user_id: int):
    cutoff = now() - 24 * 60 * 60
    cur.execute(
        """
        UPDATE orders
        SET status='cancelled'
        WHERE user_id=%s
          AND status='pending'
          AND paid_at IS NULL
          AND created_at < %s
        """,
        (int(user_id), cutoff),
    )


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


def _ledger(cur, user_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT credit_type, delta, reason, ref_table, ref_id, created_at
        FROM credit_ledger
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT 100
        """,
        (int(user_id),),
    )
    return cur.fetchall() or []


def _recommended_pack_from_invite(cur, user: dict) -> str:
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])
    if role != "winery":
        return ""

    cur.execute(
        """
        SELECT COALESCE(sc.recommended_pack, '') AS recommended_pack
        FROM wineries w
        JOIN studio_clients sc ON sc.winery_id = w.id
        WHERE w.owner_user_id=%s
          AND COALESCE(sc.recommended_pack, '') <> ''
        ORDER BY sc.created_at DESC
        LIMIT 1
        """,
        (uid,),
    )
    r = cur.fetchone() or {}
    pack = (r.get("recommended_pack") or "").strip().lower()
    if get_purchase_pack(pack):
        return pack

    cur.execute(
        """
        SELECT COALESCE(recommended_pack, '') AS recommended_pack
        FROM studio_invites
        WHERE used_by_user_id=%s
          AND used_at IS NOT NULL
        ORDER BY used_at DESC
        LIMIT 1
        """,
        (uid,),
    )
    r = cur.fetchone() or {}
    pack = (r.get("recommended_pack") or "").strip().lower()
    if get_purchase_pack(pack):
        return pack

    return ""


def _active_subscription(cur, user_id: int) -> dict:
    cur.execute(
        """
        SELECT id, plan, status, starts_at, expires_at, source_order_id
        FROM subscriptions
        WHERE user_id=%s
          AND status='active'
        ORDER BY expires_at DESC
        LIMIT 1
        """,
        (int(user_id),),
    )
    return cur.fetchone() or {}


def _plan_label(plan: str) -> str:
    data = get_purchase_pack(plan)
    if data:
        return data.get("name") or plan or "-"
    return plan or "-"


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return time.strftime("%d/%m/%Y %H:%M", time.localtime(int(ts)))
    except Exception:
        return "-"


def _subscription_box(sub: dict) -> str:
    ts = now()
    if not sub:
        return """
        <div class="billingSubscriptionBox billingSubscriptionNone">
          <div>
            <span>Piano attivo</span>
            <b>Nessun piano attivo</b>
            <small>Puoi usare eventuali crediti residui. QRFACILE oggi lavora principalmente a crediti, senza abbonamento obbligatorio.</small>
          </div>
        </div>
        """

    plan = _plan_label(sub.get("plan") or "")
    expires_at = int(sub.get("expires_at") or 0)
    days_left = max(0, int((expires_at - ts) / 86400)) if expires_at else 0
    expires_txt = _fmt_ts(expires_at)

    cls = "ok"
    alert = ""
    if days_left <= 7:
        cls = "danger"
        alert = "Scadenza imminente."
    elif days_left <= 30:
        cls = "warn"
        alert = "Il piano legacy scade entro 30 giorni."
    elif days_left <= 60:
        cls = "soft"
        alert = "Il piano legacy scade entro 60 giorni."

    alert_html = f"<div class='billingSubscriptionAlert'>{esc(alert)}</div>" if alert else ""

    return f"""
    <div class="billingSubscriptionBox {cls}">
      <div>
        <span>Piano legacy attivo</span>
        <b>{esc(plan)}</b>
        <small>Valido fino al {esc(expires_txt)}</small>
      </div>
      <div class="billingCountdown">
        <span>Giorni rimanenti</span>
        <b>{days_left}</b>
      </div>
      {alert_html}
    </div>
    """


def _orders(cur, user_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT id, pack, qty, amount_cents, currency, status, created_at, paid_at
        FROM orders
        WHERE user_id=%s
        ORDER BY id DESC
        LIMIT 20
        """,
        (int(user_id),),
    )
    return cur.fetchall() or []


def _billing_winery_id(cur, user: dict) -> int | None:
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    if role == "winery":
        cur.execute("SELECT id FROM wineries WHERE owner_user_id=%s LIMIT 1", (uid,))
        r = cur.fetchone()
        return int(r["id"]) if r and r.get("id") else None

    if role == "admin":
        cur.execute("SELECT admin_active_winery_id FROM users WHERE id=%s LIMIT 1", (uid,))
        r = cur.fetchone() or {}
        return int(r["admin_active_winery_id"]) if r.get("admin_active_winery_id") else None

    return None


def _fmt_money(cents: int | None, currency: str = "EUR") -> str:
    cents = int(cents or 0)
    return f"{cents / 100:.2f} {currency}".replace(".", ",")


def _delta_html(delta: int) -> str:
    delta = int(delta or 0)
    if delta > 0:
        return f"<span class='billingDelta billingDeltaPlus'>+{delta}</span>"
    if delta < 0:
        return f"<span class='billingDelta billingDeltaMinus'>{delta}</span>"
    return "<span class='billingDelta'>0</span>"


def _reason_label(reason: str) -> str:
    r = (reason or "").strip().lower()
    labels = {
        "seed": "Crediti iniziali",
        "purchase": "Acquisto crediti",
        "admin_adjust": "Caricamento admin",
        "new_wine": "Creazione lotto vino",
        "wine_lot_create": "Creazione QR vino",
        "new_external": "Creazione QR link",
    }
    return labels.get(r, reason or "-")


def _pack_card(pack_key: str, pack: dict, recommended_pack: str = "") -> str:
    recommended_pack = (recommended_pack or "").strip().lower()
    is_recommended = bool(recommended_pack and pack_key == recommended_pack)
    is_default_featured = (not recommended_pack and pack_key == "pro")
    featured = " featured" if (is_recommended or is_default_featured or pack.get("highlight")) else ""

    if is_recommended:
        badge = "<div class='billingPackBadge'>Consigliato dallo Studio</div>"
    elif is_default_featured or pack.get("highlight"):
        badge = "<div class='billingPackBadge'>Consigliato</div>"
    else:
        badge = ""

    wine = int(pack.get("wine_credits") or 0)
    generic = int(pack.get("generic_credits") or 0)

    if wine >= 999999:
        credits_line = "QR vino illimitati / gestione admin"
    elif wine:
        credits_line = f"{wine} crediti wine"
    elif generic:
        credits_line = f"{generic} crediti generic"
    else:
        credits_line = "Pacchetto operativo"

    disabled = bool(pack.get("disabled")) or int(pack.get("amount_cents") or 0) <= 0
    btn = """
        <button class="btn billingPackBtn" type="button" disabled>
          Non acquistabile online
        </button>
    """ if disabled else """
        <button class="btn btn-primary billingPackBtn" type="submit">
          Acquista ora
        </button>
    """

    return f"""
    <article class="billingPack{featured}">
      {badge}
      <div class="billingPackName">{esc(pack.get("name") or pack_key)}</div>
      <div class="billingPackPrice">{esc(pack.get("price") or "-")}</div>
      <div class="billingPackCredits">{esc(credits_line)}</div>
      <div class="billingPackDesc">{esc(pack.get("desc") or "")}</div>
      <form method="post" action="/paypal/start" style="margin-top:auto">
        <input type="hidden" name="pack" value="{esc(pack_key)}">
        {btn}
      </form>
    </article>
    """


@router.get("/app/billing", response_class=HTMLResponse)
def billing(request: Request, msg: str = "", err: str = ""):
    user = require_any_role(request, ("winery", "studio", "admin"))
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            _cleanup_old_pending_orders(cur, uid)
            conn.commit()
            balances = _balances(cur, uid)
            ledger = _ledger(cur, uid)
            orders = _orders(cur, uid)
            subscription = _active_subscription(cur, uid)
            recommended_pack = _recommended_pack_from_invite(cur, user)

    actions = (
        pill(f"wine: {balances.get('wine', 0)}", "green") + " " +
        pill(f"generic: {balances.get('generic', 0)}") + " " +
        top_actions(
            ("/app/start", "Menu"),
            ("/app/dashboard", "Dashboard"),
            ("/pricing", "Prezzi pubblici"),
            ("/logout", "Logout"),
        )
    )

    subscription_html = ""
    if subscription:
        subscription_html = _subscription_box(subscription)

    recommended_box = ""
    if recommended_pack:
        data = get_purchase_pack(recommended_pack)
        recommended_label = data.get("name") if data else recommended_pack
        recommended_box = f"""
        <div class="note" style="margin-top:16px;background:rgba(236,253,245,.92);border:1px solid rgba(20,184,166,.18)">
          <b>Piano consigliato dallo Studio:</b> {esc(recommended_label)}
          <br>
          Puoi acquistare questo pacchetto oppure sceglierne un altro.
        </div>
        """

    hidden_packs = {"unlimited"}
    visible_packs = [
        (k, v)
        for k, v in list_billing_packs()
        if not v.get("hidden_in_billing") and k not in hidden_packs
    ]

    pack_cards = "".join(_pack_card(k, v, recommended_pack) for k, v in visible_packs)

    ledger_rows = ""
    for r in ledger:
        credit_type = esc(r.get("credit_type") or "")
        delta = _delta_html(int(r.get("delta") or 0))
        reason = esc(_reason_label(r.get("reason") or ""))
        ref = ""
        if r.get("ref_table") or r.get("ref_id"):
            ref = f"{esc(r.get('ref_table') or '')} #{esc(str(r.get('ref_id') or ''))}"
        created = esc(_fmt_ts(int(r.get("created_at") or 0)))
        ledger_rows += f"""
        <tr>
          <td><span class="billingType">{credit_type}</span></td>
          <td>{delta}</td>
          <td>{reason}</td>
          <td>{esc(ref or "-")}</td>
          <td>{created}</td>
        </tr>
        """

    if not ledger_rows:
        ledger_rows = """
        <tr>
          <td colspan="5">
            <div class="billingEmptyTable">Nessun movimento credito ancora presente.</div>
          </td>
        </tr>
        """

    order_cards = ""
    for o in orders:
        pack_key = (o.get("pack") or "-").strip().lower()
        data = get_purchase_pack(pack_key)
        pack_label = data.get("name") if data else pack_key
        amount = esc(_fmt_money(o.get("amount_cents"), o.get("currency") or "EUR"))
        status = esc(o.get("status") or "-")
        created = esc(_fmt_ts(int(o.get("created_at") or 0)))
        order_cards += f"""
        <div class="billingOrderRow">
          <div>
            <b>{esc(pack_label)}</b>
            <span>Richiesta del {created}</span>
          </div>
          <div>
            <b>{amount}</b>
            <span>{status}</span>
          </div>
        </div>
        """

    if not order_cards:
        order_cards = """
        <div class="billingEmptyOrders">Nessun ordine ancora presente.</div>
        """

    body = f"""
    <section class="billingWrap">
      <div class="billingHero">
        <div>
          <div class="billingEyebrow">Crediti QR</div>
          <div class="h1">Billing</div>
          <div class="p">
            Controlla il saldo disponibile e acquista crediti QR o servizi opzionali di Assistenza QRFACILE. Nessun abbonamento obbligatorio.
          </div>
        </div>
        <div class="billingHeroCards">
          <div class="billingHeroCard billingWine">
            <span>Crediti wine</span>
            <b>{int(balances.get("wine", 0))}</b>
            <small>10 anni = 1 credito · 25 anni = 2 crediti</small>
          </div>
          <div class="billingHeroCard billingGeneric">
            <span>Crediti generic</span>
            <b>{int(balances.get("generic", 0))}</b>
            <small>QR link esterni/generici</small>
          </div>
        </div>
      </div>

      <div class="billingNotice">
        <b>Regola principale:</b> 1 credito crea un QR vino da 10 anni. 2 crediti creano un QR vino da 25 anni.
      </div>

      {subscription_html}
      {recommended_box}

      <div class="billingPackGrid">
        {pack_cards}
      </div>

      <div class="billingGrid">
        <div class="card billingInfoCard">
          <div class="billingCardIcon">ℹ️</div>
          <div>
            <div class="h2">Come funzionano i crediti</div>
            <div class="billingRules">
              <div><b>Wine credits</b><span>Servono per creare QR vino/lotti: 1 credito = QR da 10 anni, 2 crediti = QR da 25 anni.</span></div>
              <div><b>Generic credits</b><span>Servono per QR link esterni o contenuti non vino.</span></div>
              <div><b>Pubblicazione</b><span>La pubblicazione può essere bloccata se mancano dati obbligatori.</span></div>
              <div><b>Pagamento</b><span>Il pagamento online carica automaticamente i crediti acquistati. I servizi assistiti non caricano crediti.</span></div>
            </div>
          </div>
        </div>

        <div class="card billingOrdersCard">
          <div class="billingCardIcon">📄</div>
          <div class="h2">Ordini</div>
          <div class="p">Ultimi ordini o richieste di acquisto.</div>
          <div class="billingOrdersList">{order_cards}</div>
        </div>
      </div>

      <div class="card billingHistoryCard">
        <div class="billingHistoryHead">
          <div>
            <div class="h2">Movimenti crediti</div>
            <div class="p">Ultimi 100 movimenti credito collegati al tuo account.</div>
          </div>
        </div>
        <div class="billingTableWrap">
          <table>
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Delta</th>
                <th>Motivo</th>
                <th>Riferimento</th>
                <th>Data</th>
              </tr>
            </thead>
            <tbody>{ledger_rows}</tbody>
          </table>
        </div>
      </div>

      <style>
        .billingWrap {{ max-width:1180px; margin:0 auto; }}
        .billingHero {{
          border:1px solid rgba(2,8,23,.08); border-radius:28px; overflow:hidden;
          box-shadow:0 24px 80px rgba(2,8,23,.08);
          background:radial-gradient(circle at 8% 12%, rgba(191,245,230,.58), transparent 34%),
                     radial-gradient(circle at 92% 8%, rgba(207,232,255,.58), transparent 34%),
                     linear-gradient(135deg,rgba(255,255,255,.96),rgba(248,252,250,.92));
          padding:30px; display:grid; grid-template-columns:minmax(0,1.2fr) 420px; gap:24px; align-items:end;
        }}
        .billingEyebrow {{ display:inline-flex; padding:7px 12px; border-radius:999px; background:rgba(20,184,166,.10); color:#0f766e; font-size:12px; font-weight:950; letter-spacing:.08em; text-transform:uppercase; }}
        .billingHeroCards {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
        .billingHeroCard {{ border:1px solid rgba(2,8,23,.07); border-radius:24px; padding:18px; background:rgba(255,255,255,.72); }}
        .billingHeroCard span {{ display:block; color:#64748b; font-size:12px; font-weight:950; text-transform:uppercase; letter-spacing:.07em; }}
        .billingHeroCard b {{ display:block; margin-top:8px; font-size:42px; line-height:1; font-weight:950; }}
        .billingHeroCard small {{ display:block; margin-top:8px; color:#64748b; font-size:12px; font-weight:750; line-height:1.35; }}
        .billingWine {{ background:rgba(236,253,245,.82); }}
        .billingGeneric {{ background:rgba(239,246,255,.82); }}
        .billingNotice {{ margin-top:18px; border:1px solid rgba(20,184,166,.16); background:rgba(236,253,245,.78); color:#0f766e; border-radius:22px; padding:16px; font-size:14px; font-weight:780; line-height:1.45; }}
        .billingSubscriptionBox {{ margin-top:18px; border:1px solid rgba(20,184,166,.18); border-radius:24px; background:rgba(236,253,245,.78); box-shadow:0 14px 45px rgba(2,8,23,.055); padding:18px; display:grid; grid-template-columns:minmax(0,1fr) 180px; gap:16px; align-items:center; }}
        .billingSubscriptionBox span {{ display:block; color:#64748b; font-size:11px; font-weight:950; text-transform:uppercase; letter-spacing:.07em; }}
        .billingSubscriptionBox b {{ display:block; margin-top:6px; font-size:24px; font-weight:950; color:#0f172a; }}
        .billingSubscriptionBox small {{ display:block; margin-top:6px; color:#64748b; font-size:13px; font-weight:750; line-height:1.4; }}
        .billingSubscriptionNone {{ background:rgba(248,250,252,.88); border-color:rgba(2,8,23,.08); grid-template-columns:1fr; }}
        .billingSubscriptionBox.soft {{ background:rgba(239,246,255,.84); border-color:rgba(59,130,246,.18); }}
        .billingSubscriptionBox.warn {{ background:rgba(255,251,235,.86); border-color:rgba(245,158,11,.22); }}
        .billingSubscriptionBox.danger {{ background:rgba(255,241,242,.86); border-color:rgba(244,63,94,.22); }}
        .billingCountdown {{ border:1px solid rgba(2,8,23,.07); background:rgba(255,255,255,.75); border-radius:20px; padding:14px; text-align:center; }}
        .billingCountdown b {{ font-size:42px; line-height:1; color:#0f766e; }}
        .billingSubscriptionAlert {{ grid-column:1 / -1; border-top:1px solid rgba(2,8,23,.08); padding-top:12px; color:#92400e; font-size:13px; font-weight:850; line-height:1.45; }}
        .billingPackGrid {{ margin-top:18px; display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:14px; }}
        .billingPack {{ position:relative; border:1px solid rgba(2,8,23,.08); border-radius:24px; background:rgba(255,255,255,.88); box-shadow:0 14px 45px rgba(2,8,23,.055); padding:18px; min-height:270px; display:flex; flex-direction:column; }}
        .billingPack.featured {{ border-color:rgba(20,184,166,.26); background:radial-gradient(circle at 100% 0%, rgba(191,245,230,.42), transparent 34%), rgba(255,255,255,.94); }}
        .billingPackBadge {{ position:absolute; top:14px; right:14px; background:#0f766e; color:#fff; border-radius:999px; padding:6px 9px; font-size:10px; font-weight:950; text-transform:uppercase; letter-spacing:.06em; }}
        .billingPackName {{ font-size:20px; font-weight:950; color:#0f172a; }}
        .billingPackPrice {{ margin-top:12px; font-size:28px; font-weight:950; letter-spacing:-.8px; }}
        .billingPackCredits {{ margin-top:7px; color:#0f766e; font-size:13px; font-weight:950; }}
        .billingPackDesc {{ margin-top:10px; color:#64748b; font-size:13px; line-height:1.45; font-weight:750; flex:1; }}
        .billingPackBtn {{ width:100%; justify-content:center; margin-top:16px; }}
        .billingGrid {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; margin-top:18px; }}
        .billingInfoCard, .billingOrdersCard {{ padding:22px; }}
        .billingCardIcon {{ width:58px; height:58px; border-radius:20px; display:flex; align-items:center; justify-content:center; background:linear-gradient(135deg,rgba(191,245,230,.85),rgba(207,232,255,.85)); font-size:26px; margin-bottom:14px; border:1px solid rgba(2,8,23,.06); }}
        .billingRules {{ display:grid; gap:10px; margin-top:16px; }}
        .billingRules div {{ border:1px solid rgba(2,8,23,.07); border-radius:18px; padding:13px; background:rgba(255,255,255,.70); }}
        .billingRules b {{ display:block; font-size:14px; font-weight:950; }}
        .billingRules span {{ display:block; margin-top:5px; color:#64748b; font-size:12px; line-height:1.35; font-weight:750; }}
        .billingOrdersList {{ display:grid; gap:10px; margin-top:16px; }}
        .billingOrderRow {{ display:flex; justify-content:space-between; gap:12px; border:1px solid rgba(2,8,23,.07); border-radius:18px; padding:13px; background:rgba(255,255,255,.70); }}
        .billingOrderRow b {{ display:block; font-size:13px; font-weight:950; }}
        .billingOrderRow span {{ display:block; margin-top:4px; color:#64748b; font-size:12px; font-weight:750; }}
        .billingEmptyOrders {{ border:1px dashed rgba(2,8,23,.16); border-radius:18px; padding:16px; color:#64748b; font-size:13px; font-weight:750; text-align:center; }}
        .billingHistoryCard {{ margin-top:18px; padding:22px; }}
        .billingHistoryHead {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:16px; }}
        .billingTableWrap {{ overflow:auto; border:1px solid rgba(2,8,23,.07); border-radius:20px; }}
        .billingTableWrap table {{ width:100%; border-collapse:collapse; min-width:760px; background:#fff; }}
        .billingTableWrap th, .billingTableWrap td {{ padding:12px 13px; border-bottom:1px solid rgba(2,8,23,.07); text-align:left; font-size:13px; }}
        .billingTableWrap th {{ color:#64748b; font-size:11px; font-weight:950; text-transform:uppercase; letter-spacing:.06em; background:rgba(248,250,252,.88); }}
        .billingType {{ display:inline-flex; padding:6px 9px; border-radius:999px; background:rgba(239,246,255,.82); border:1px solid rgba(59,130,246,.15); color:#1d4ed8; font-size:12px; font-weight:950; }}
        .billingDelta {{ display:inline-flex; padding:6px 9px; border-radius:999px; background:rgba(248,250,252,.88); border:1px solid rgba(2,8,23,.08); font-weight:950; font-size:12px; }}
        .billingDeltaPlus {{ color:#0f766e; background:rgba(236,253,245,.82); border-color:rgba(20,184,166,.18); }}
        .billingDeltaMinus {{ color:#be123c; background:rgba(255,241,242,.82); border-color:rgba(244,63,94,.16); }}
        .billingEmptyTable {{ padding:20px; text-align:center; color:#64748b; font-weight:750; }}
        @media(max-width:1180px) {{ .billingPackGrid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} }}
        @media(max-width:980px) {{ .billingHero, .billingGrid {{ grid-template-columns:1fr; }} .billingHeroCards {{ max-width:520px; }} }}
        @media(max-width:640px) {{ .billingHero {{ padding:22px; }} .billingHeroCards, .billingSubscriptionBox {{ grid-template-columns:1fr; }} .billingPackGrid {{ grid-template-columns:1fr; }} }}
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Billing",
        subtitle="Crediti QR",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=user.get("email", ""),
        role=role,
        credits=balances,
    ))


@router.post("/app/billing/request-plan")
def request_plan(request: Request, pack: str = Form(...)):
    user = require_any_role(request, ("winery", "admin"))
    pack = (pack or "").strip().lower()

    data = get_purchase_pack(pack)
    if not data:
        raise HTTPException(400, "Piano non valido")

    if data.get("disabled") or int(data.get("amount_cents") or 0) <= 0:
        raise HTTPException(400, "Piano non acquistabile online")

    uid = int(user["id"])

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            winery_id = _billing_winery_id(cur, user)
            cur.execute(
                """
                INSERT INTO orders (
                  user_id,
                  billing_winery_id,
                  pack,
                  qty,
                  amount_cents,
                  currency,
                  status,
                  created_at
                )
                VALUES (%s,%s,%s,%s,%s,'EUR','pending',%s)
                RETURNING id
                """,
                (
                    uid,
                    winery_id,
                    pack,
                    1,
                    int(data["amount_cents"]),
                    now(),
                ),
            )
            order_id = int(cur.fetchone()["id"])
            conn.commit()

    return RedirectResponse(
        f"/app/billing?msg=Richiesta%20piano%20registrata%20%28ordine%20%23{order_id}%29",
        status_code=303,
    )
