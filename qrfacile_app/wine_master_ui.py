import time
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.auth_core import require_any_role, studio_allowed_wineries, winery_id_for_owner
from qrfacile_app.ui_shell import page, top_actions, pill, esc

router = APIRouter()

def now() -> int:
    return int(time.time())

def _allowed_winery_ids(user: dict, need: str = "view") -> list[int]:
    role = (user.get("role") or "").lower().strip()
    if role == "admin":
        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id FROM wineries ORDER BY id")
                return [int(r["id"]) for r in (cur.fetchall() or [])]
    if role == "studio":
        return studio_allowed_wineries(int(user["id"]), need=need)
    wid = winery_id_for_owner(int(user["id"]))
    return [wid] if wid else []

def _wineries(cur, ids: list[int]) -> list[dict]:
    cur.execute(
        """
        SELECT id AS winery_id, name
        FROM wineries
        WHERE id = ANY(%s)
        ORDER BY lower(name)
        """,
        (ids,),
    )
    return cur.fetchall() or []

@router.get("/app/new-wine-master", response_class=HTMLResponse)
def new_wine_master_get(request: Request, winery_id: int = 0, msg: str = "", err: str = ""):
    u = require_any_role(request, ("winery", "studio", "admin"))
    role = (u.get("role") or "").lower().strip()
    allowed_view = _allowed_winery_ids(u, need="view")
    allowed_create = _allowed_winery_ids(u, need="create")

    if not allowed_view:
        return HTMLResponse(page(
            title="QRFACILE · Nuova etichetta",
            subtitle="Nuova etichetta",
            body_html="<div class='card'><div class='h2'>Nessuna cantina disponibile</div></div>",
            err="Nessuna cantina",
            user_email=str(u.get("email") or ""),
            role=role,
            credits=u.get("credits") if isinstance(u.get("credits"), dict) else None,
        ), status_code=200)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            wlist = _wineries(cur, allowed_view)

    actions = top_actions(("/app/start", "Menu"), ("/app/dashboard", "Dashboard"), ("/logout", "Logout"))
    body = f"""
    <div class="h1" style="margin-top:14px">Nuova etichetta</div>
    <div class="p">Crea una nuova etichetta/prodotto. I lotti verranno creati dopo.</div>

    <form class="card" method="post" action="/app/new-wine-master" style="margin-top:14px;max-width:900px">
      <label>Cantina</label>
      <select name="winery_id" required>
        {''.join([f"<option value='{int(w['winery_id'])}' {'selected' if int(w['winery_id'])==int(winery_id or 0) else ''}>{esc(w.get('name') or '')}</option>" for w in wlist])}
      </select>

      <label style="margin-top:12px">Nome etichetta/prodotto</label>
      <input class="input" name="name" placeholder="es. Falanghina del Sannio DOC" required>

      <div class="note" style="margin-top:12px">
        Nota: questa è la scheda etichetta/prodotto. Ogni lotto collegato genererà il proprio QR definitivo.
      </div>

      <div class="row" style="margin-top:14px">
        <button class="btn btn-primary" type="submit">Crea etichetta</button>
        <a class="btn" href="/app/new-wine">Crea subito un lotto</a>
      </div>
    </form>
    """
    return HTMLResponse(page(
        title="QRFACILE · Nuova etichetta",
        subtitle="Nuova etichetta",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=u.get("email",""),
        role=role,
        credits=None,
    ))

@router.post("/app/new-wine-master")
def new_wine_master_post(request: Request, winery_id: int = Form(...), name: str = Form(...)):
    u = require_any_role(request, ("winery", "studio", "admin"))

    # enforce create
    require_any_role(request, ("winery", "studio", "admin"), winery_id=int(winery_id), need="create")

    nm = (name or "").strip()
    if not nm:
        return RedirectResponse("/app/new-wine-master?err=Nome%20obbligatorio", status_code=303)

    ts = now()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # upsert (winery_id, lower(name))
            cur.execute(
                """
                SELECT id
                FROM wines_master
                WHERE winery_id=%s AND lower(name)=lower(%s)
                LIMIT 1
                """,
                (int(winery_id), nm),
            )
            r = cur.fetchone()
            if r:
                wine_master_id = int(r["id"])
            else:
                cur.execute(
                    """
                    INSERT INTO wines_master (winery_id, name, created_at, updated_at)
                    VALUES (%s,%s,%s,%s)
                    RETURNING id
                    """,
                    (int(winery_id), nm, ts, ts),
                )
                wine_master_id = int(cur.fetchone()["id"])
            conn.commit()

    return RedirectResponse(f"/app/new-wine?winery_id={int(winery_id)}&wine_master_id={wine_master_id}&msg=Etichetta%20creata", status_code=303)
