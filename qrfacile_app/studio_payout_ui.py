from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, esc, pill

router = APIRouter()


MIN_PAYOUT = 200.0


def _balances(cur, user_id: int) -> dict:
    cur.execute("""
        SELECT
          SUM(CASE WHEN status='maturing' THEN amount_eur ELSE 0 END) AS maturing,
          SUM(CASE WHEN status='available' THEN amount_eur ELSE 0 END) AS available,
          SUM(CASE WHEN status='requested' THEN amount_eur ELSE 0 END) AS requested,
          SUM(CASE WHEN status='paid' THEN amount_eur ELSE 0 END) AS paid
        FROM commission_ledger
        WHERE studio_user_id=%s
    """, (int(user_id),))
    r = cur.fetchone() or {}
    return {
        "maturing": float(r.get("maturing") or 0),
        "available": float(r.get("available") or 0),
        "requested": float(r.get("requested") or 0),
        "paid": float(r.get("paid") or 0),
    }


def _credits(cur, user_id: int) -> dict:
    cur.execute("""
        SELECT credit_type, COALESCE(SUM(delta),0) AS bal
        FROM credit_ledger
        WHERE user_id=%s
        GROUP BY credit_type
    """, (int(user_id),))
    out = {"wine": 0, "generic": 0}
    for r in (cur.fetchall() or []):
        out[r["credit_type"]] = int(r["bal"])
    return out


@router.get("/studio/commissions", response_class=HTMLResponse)
def studio_commissions(request: Request, msg: str = "", err: str = ""):
    u = require_any_role(request, ("studio",))
    uid = int(u["id"])
    email = u.get("email") or ""

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            balances = _balances(cur, uid)
            credits = _credits(cur, uid)

    actions = f"""
        <a class="btn" href="/app/start">Menu</a>
        <a class="btn" href="/logout">Logout</a>
    """

    summary = f"""
    <div class="card" style="margin-top:14px">
        <div class="h2">Riepilogo Commissioni</div>

        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:14px" class="grid2">

            <div class="card">
                {pill("Maturing")}
                <div style="font-size:22px;font-weight:900;margin-top:10px">
                    {balances["maturing"]:.2f}€
                </div>
            </div>

            <div class="card">
                {pill("Available","green")}
                <div style="font-size:22px;font-weight:900;margin-top:10px">
                    {balances["available"]:.2f}€
                </div>
            </div>

            <div class="card">
                {pill("Requested")}
                <div style="font-size:22px;font-weight:900;margin-top:10px">
                    {balances["requested"]:.2f}€
                </div>
            </div>

            <div class="card">
                {pill("Paid")}
                <div style="font-size:22px;font-weight:900;margin-top:10px">
                    {balances["paid"]:.2f}€
                </div>
            </div>

        </div>
    </div>
    """

    payout_section = ""

    if balances["available"] >= MIN_PAYOUT:
        payout_section = f"""
        <div class="card" style="margin-top:14px">
            <div class="h2">Richiedi pagamento</div>
            <div class="p">Importo disponibile: <b>{balances["available"]:.2f}€</b></div>

            <form method="post" action="/studio/request-payout" style="margin-top:14px">
                <label>IBAN</label>
                <input class="input" name="iban" required>

                <label>Beneficiario</label>
                <input class="input" name="beneficiary" required>

                <div style="margin-top:14px">
                    <button class="btn btn-primary" type="submit">
                        Richiedi Payout
                    </button>
                </div>
            </form>
        </div>
        """
    else:
        payout_section = f"""
        <div class="card" style="margin-top:14px">
            <div class="h2">Richiedi pagamento</div>
            <div class="p">Minimo payout: {MIN_PAYOUT:.0f}€</div>
            <div class="note" style="margin-top:12px">
                Soglia non raggiunta
            </div>
        </div>
        """

    body = summary + payout_section

    return HTMLResponse(page(
        title="QRFACILE",
        subtitle="Commissioni Studio",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=email,
        role="studio",
        credits=credits,
    ))


@router.post("/studio/request-payout")
def request_payout(
    request: Request,
    iban: str = Form(...),
    beneficiary: str = Form(...),
):
    u = require_any_role(request, ("studio",))
    uid = int(u["id"])

    iban = (iban or "").strip()
    beneficiary = (beneficiary or "").strip()

    if not iban or not beneficiary:
        return RedirectResponse(
            "/studio/commissions?err=Dati%20non%20validi",
            status_code=303
        )

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            balances = _balances(cur, uid)
            available = balances["available"]

            if available < MIN_PAYOUT:
                conn.rollback()
                return RedirectResponse(
                    "/studio/commissions?err=Soglia%20non%20raggiunta",
                    status_code=303
                )

            # sposta commissioni available -> requested
            cur.execute("""
                UPDATE commission_ledger
                SET status='requested'
                WHERE studio_user_id=%s AND status='available'
            """, (uid,))

            cur.execute("""
                INSERT INTO payout_requests
                  (studio_user_id, amount_eur, iban, beneficiary, status)
                VALUES (%s,%s,%s,%s,'requested')
            """, (uid, available, iban, beneficiary))

            conn.commit()

    return RedirectResponse(
        "/studio/commissions?msg=Richiesta%20inviata",
        status_code=303
    )
