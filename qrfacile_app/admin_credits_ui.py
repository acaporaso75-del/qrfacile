import time
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, esc

router = APIRouter()


def _now_epoch() -> int:
    return int(time.time())


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))
    except Exception:
        return "-"


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


def _find_users(cur, q: str) -> list[dict]:
    q = (q or "").strip()
    if not q:
        return []

    if q.isdigit():
        cur.execute(
            """
            SELECT id, email, role
            FROM users
            WHERE id=%s
            ORDER BY id DESC
            LIMIT 20
            """,
            (int(q),),
        )
        return cur.fetchall() or []

    like = f"%{q.lower()}%"
    cur.execute(
        """
        SELECT id, email, role
        FROM users
        WHERE lower(email) LIKE %s
        ORDER BY id DESC
        LIMIT 20
        """,
        (like,),
    )
    return cur.fetchall() or []


def _recent_manual_entries(cur) -> list[dict]:
    cur.execute(
        """
        SELECT
          cl.user_id,
          u.email,
          u.role,
          cl.credit_type,
          cl.delta,
          cl.reason,
          cl.ref_table,
          cl.ref_id,
          cl.created_at
        FROM credit_ledger cl
        JOIN users u ON u.id = cl.user_id
        WHERE cl.reason LIKE 'admin_manual_%'
        ORDER BY cl.created_at DESC
        LIMIT 50
        """
    )
    return cur.fetchall() or []


@router.get("/admin/credits", response_class=HTMLResponse)
def admin_credits_page(request: Request, q: str = "", msg: str = "", err: str = ""):
    u = require_any_role(request, ("admin",))
    q = (q or "").strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            users = _find_users(cur, q) if q else []
            recent = _recent_manual_entries(cur)

            enriched = []
            for usr in users:
                bal = _balances(cur, int(usr["id"]))
                enriched.append({
                    **usr,
                    "bal_wine": bal.get("wine", 0),
                    "bal_generic": bal.get("generic", 0),
                })

    actions = top_actions(
        ("/admin", "Admin"),
        ("/app/dashboard", "Dashboard"),
        ("/logout", "Logout"),
    )

    search_html = f"""
    <div class="card" style="margin-top:14px">
      <div class="h2">Carica crediti manualmente</div>
      <div class="p">
        Cerca un utente per email o ID. Puoi usare questa funzione sia per prove interne
        sia per regalare crediti.
      </div>

      <form method="get" action="/admin/credits" style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap">
        <input class="input" name="q" value="{esc(q)}" placeholder="Email utente o ID..." style="min-width:320px">
        <button class="btn btn-primary" type="submit">Cerca</button>
        <a class="btn" href="/admin/credits">Reset</a>
      </form>
    </div>
    """

    users_html = ""
    if q:
        if not enriched:
            users_html = f"""
            <div class="card" style="margin-top:14px">
              <div class="h2">Risultati</div>
              <div class="p">Nessun utente trovato per: <b>{esc(q)}</b></div>
            </div>
            """
        else:
            blocks = []
            for usr in enriched:
                blocks.append(f"""
                <div class="card" style="margin-top:14px">
                  <div class="h2">{esc(usr.get("email") or "")}</div>
                  <div class="p">
                    ID: <b>{int(usr['id'])}</b> · ruolo: <b>{esc(usr.get('role') or '')}</b>
                  </div>

                  <div class="note" style="margin-top:10px">
                    Saldo attuale · wine: <b>{int(usr.get('bal_wine') or 0)}</b> · generic: <b>{int(usr.get('bal_generic') or 0)}</b>
                  </div>

                  <form method="post" action="/admin/credits/load" style="margin-top:12px">
                    <input type="hidden" name="target_user_id" value="{int(usr['id'])}">

                    <div class="grid2">
                      <div>
                        <label>Tipo credito</label>
                        <select name="credit_type">
                          <option value="wine">wine</option>
                          <option value="generic">generic</option>
                        </select>
                      </div>

                      <div>
                        <label>Quantità</label>
                        <input class="input" name="delta" value="10" placeholder="es. 10 oppure -5">
                      </div>
                    </div>

                    <div style="margin-top:12px">
                      <label>Nota interna</label>
                      <input class="input" name="note" placeholder="es. test interno / regalo commerciale / correzione manuale">
                    </div>

                    <div class="row" style="margin-top:14px;gap:10px;flex-wrap:wrap">
                      <button class="btn btn-primary" type="submit">Salva movimento</button>
                    </div>
                  </form>
                </div>
                """)
            users_html = "".join(blocks)

    recent_rows = []
    for r in recent:
        delta = int(r.get("delta") or 0)
        sign = "+" if delta > 0 else ""
        recent_rows.append(f"""
        <tr>
          <td>{esc(_fmt_ts(r.get("created_at")))}</td>
          <td>{esc(r.get("email") or "")}</td>
          <td>{esc(r.get("role") or "")}</td>
          <td>{esc(r.get("credit_type") or "")}</td>
          <td><b>{sign}{delta}</b></td>
          <td>{esc(r.get("reason") or "")}</td>
          <td>{esc(str(r.get("ref_id") or "-"))}</td>
        </tr>
        """)

    recent_html = f"""
    <div class="card" style="margin-top:14px">
      <div class="h2">Ultimi movimenti manuali</div>
      <div style="margin-top:12px;overflow:auto">
        <table>
          <thead>
            <tr>
              <th>Data</th>
              <th>Utente</th>
              <th>Ruolo</th>
              <th>Tipo</th>
              <th>Delta</th>
              <th>Reason</th>
              <th>Admin ID</th>
            </tr>
          </thead>
          <tbody>
            {''.join(recent_rows) if recent_rows else "<tr><td colspan='7' class='muted'>Nessun movimento manuale.</td></tr>"}
          </tbody>
        </table>
      </div>
    </div>
    """

    body = f"""
    <div class="h1" style="margin-top:14px">Crediti manuali</div>
    <div class="p">Funzione admin per test, regali e correzioni manuali.</div>

    {search_html}
    {users_html}
    {recent_html}
    """

    return HTMLResponse(page(
        title="QRFACILE · Crediti manuali",
        subtitle="Admin · Crediti manuali",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=u.get("email", ""),
        role="admin",
        credits=None,
    ))


@router.post("/admin/credits/load")
def admin_credits_load(
    request: Request,
    target_user_id: int = Form(...),
    credit_type: str = Form(...),
    delta: str = Form(...),
    note: str = Form(""),
):
    u = require_any_role(request, ("admin",))
    admin_id = int(u["id"])

    credit_type = (credit_type or "").strip().lower()
    if credit_type not in ("wine", "generic"):
        raise HTTPException(400, "Tipo credito non valido")

    try:
        delta_int = int(str(delta).strip())
    except Exception:
        raise HTTPException(400, "Quantità non valida")

    if delta_int == 0:
        raise HTTPException(400, "La quantità non può essere zero")

    note = (note or "").strip()[:250]
    reason = "admin_manual_load" if delta_int > 0 else "admin_manual_adjust"
    if note:
        reason = f"{reason}:{note}"

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, email FROM users WHERE id=%s LIMIT 1", (int(target_user_id),))
            tgt = cur.fetchone()
            if not tgt:
                raise HTTPException(404, "Utente non trovato")

            cur.execute(
                """
                INSERT INTO credit_ledger
                  (user_id, credit_type, delta, reason, ref_table, ref_id, created_at)
                VALUES
                  (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    int(target_user_id),
                    credit_type,
                    delta_int,
                    reason,
                    "admin_manual",
                    admin_id,
                    _now_epoch(),
                ),
            )
            conn.commit()

    return RedirectResponse(
        f"/admin/credits?q={int(target_user_id)}&msg=Movimento%20salvato",
        status_code=303,
    )
