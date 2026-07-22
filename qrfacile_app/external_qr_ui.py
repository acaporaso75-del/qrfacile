from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page
from qrfacile_app.util import new_slug

router = APIRouter()


def now() -> int:
    import time
    return int(time.time())


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


@router.get("/app/new-external", response_class=HTMLResponse)
def new_external_get(request: Request, msg: str = "", err: str = ""):
    u = require_any_role(request, ("winery", "studio", "admin"))
    uid = int(u["id"])
    email = (u.get("email") or "").strip()
    role = (u.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            credits = _balances(cur, uid)
            cur.execute(
                "SELECT COUNT(*) AS c FROM qr_items WHERE owner_user_id=%s AND qr_type='external'",
                (uid,),
            )
            n_ext = int((cur.fetchone() or {}).get("c") or 0)

    header_actions = """
      <a class="btn" href="/app/billing">Crediti</a>
      <a class="btn" href="/app/dashboard">Dashboard</a>
      <a class="btn btn-primary" href="/app/new-wine">Nuovo lotto</a>
    """

    body = f"""
    <div class="h1" style="margin-top:14px">QR Link</div>
    <div class="p">Hai <b>3</b> QR link gratuiti. Dal 4° si scala <b>1 credito generic</b>.</div>

    <div class="card" style="margin-top:14px;max-width:980px">
      <div class="h2">Crea un QR per un link</div>
      <div class="p" style="margin-top:8px">QR link creati finora: <b>{n_ext}</b></div>

      <form method="post" action="/app/new-external/create" style="margin-top:14px">
        <label>URL destinazione</label>
        <input class="input" name="target_url" placeholder="https://..." required>

        <div class="row" style="margin-top:14px">
          <button class="btn btn-primary" type="submit">Crea QR Link</button>
          <a class="btn" href="/app/dashboard">Torna alla dashboard</a>
        </div>
      </form>

      <div class="note" style="margin-top:14px">
        Usa URL completi <span class="mono">https://</span>. Il QR punta a un URL pubblico stabile.
      </div>
    </div>
    """

    return HTMLResponse(page(
        title="QRFACILE",
        subtitle="QR Link",
        body_html=body,
        actions_html=header_actions,
        msg=msg,
        err=err,
        user_email=email,
        role=role,
        credits=credits,
    ))


@router.post("/app/new-external/create")
def new_external_create(request: Request, target_url: str = Form(...)):
    u = require_any_role(request, ("winery", "studio", "admin"))
    uid = int(u["id"])

    target_url = (target_url or "").strip()
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        return RedirectResponse("/app/new-external?err=URL%20non%20valida", status_code=303)

    ts = now()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM qr_items WHERE owner_user_id=%s AND qr_type='external'",
                (uid,),
            )
            external_count = int((cur.fetchone() or {}).get("c") or 0)

            if external_count >= 3:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(delta),0) AS balance
                    FROM credit_ledger
                    WHERE user_id=%s AND credit_type='generic'
                    """,
                    (uid,),
                )
                bal = int((cur.fetchone() or {}).get("balance") or 0)
                if bal < 1:
                    conn.rollback()
                    return RedirectResponse("/app/billing?error=crediti_insufficienti", status_code=303)

            slug = new_slug()
            public_path = f"/e/{slug}"

            cur.execute(
                """
                INSERT INTO qr_items(
                  owner_user_id, winery_id, qr_type, status, slug, title,
                  has_back, public_path, payload, created_at, updated_at
                )
                VALUES (%s,NULL,'external','attiva',%s,%s,0,%s,
                        jsonb_build_object('url', %s::text),
                        %s,%s)
                RETURNING id
                """,
                (uid, slug, "Link esterno", public_path, target_url, ts, ts),
            )
            qr_id = int(cur.fetchone()["id"])

            if external_count >= 3:
                cur.execute(
                    """
                    INSERT INTO credit_ledger
                      (user_id, credit_type, delta, reason, ref_table, ref_id, created_at)
                    VALUES (%s,'generic',-1,'simple_qr_extra','qr_items',%s,%s)
                    """,
                    (uid, qr_id, ts),
                )

            conn.commit()

    return RedirectResponse(f"/app/external/{qr_id}?msg=QR%20creato", status_code=303)


@router.get("/app/external/{qr_id}", response_class=HTMLResponse)
def external_detail(request: Request, qr_id: int, msg: str = "", err: str = ""):
    u = require_any_role(request, ("winery", "studio", "admin"))
    uid = int(u["id"])
    email = (u.get("email") or "").strip()
    role = (u.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            credits = _balances(cur, uid)

            cur.execute(
                """
                SELECT id, owner_user_id, public_path, payload, slug
                FROM qr_items
                WHERE id=%s AND qr_type='external'
                LIMIT 1
                """,
                (int(qr_id),),
            )
            r = cur.fetchone()
            if not r:
                raise HTTPException(404, "QR non trovato")

            if int(r["owner_user_id"]) != uid and role != "admin":
                raise HTTPException(403, "Forbidden")

            public_url = r.get("public_path") or ""
            payload = r.get("payload")
            target = ""
            if isinstance(payload, dict):
                target = payload.get("url") or ""

    header_actions = """
      <a class="btn" href="/app/new-external">Nuovo QR Link</a>
      <a class="btn" href="/app/billing">Crediti</a>
      <a class="btn" href="/app/dashboard">Dashboard</a>
    """

    body = f"""
    <div class="h1" style="margin-top:14px">QR Link creato</div>
    <div class="p">Questo QR punta a un URL pubblico stabile. La destinazione può essere aggiornata in futuro.</div>

    <div class="card" style="margin-top:14px;max-width:980px">
      <div class="h2">Dettagli</div>

      <div class="note" style="margin-top:12px">
        <b>URL pubblico:</b> <a href="{public_url}" target="_blank" rel="noopener">{public_url}</a>
      </div>

      <div class="note" style="margin-top:12px">
        <b>Destinazione:</b> <span class="mono">{target}</span>
      </div>

      <div class="row" style="margin-top:14px">
        <a class="btn btn-primary" href="{public_url}" target="_blank" rel="noopener">Apri URL pubblico</a>
        <a class="btn" href="/app/new-external">Crea un altro QR</a>
      </div>

      <div class="note" style="margin-top:14px">
        Tip: stampa sempre il QR sull’URL pubblico, non sulla destinazione.
      </div>
    </div>
    """

    return HTMLResponse(page(
        title="QRFACILE",
        subtitle="QR Link",
        body_html=body,
        actions_html=header_actions,
        msg=msg,
        err=err,
        user_email=email,
        role=role,
        credits=credits,
    ))
