from urllib.parse import urlsplit

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.csrf_core import csrf_input
from qrfacile_app.ui_shell import esc, page
from qrfacile_app.util import new_slug
from qrfacile_app.modules.switches import is_enabled

router = APIRouter()


def now() -> int:
    import time
    return int(time.time())


def _balances(cur, user_id: int) -> dict:
    cur.execute(
        """
        SELECT credit_type, COALESCE(SUM(delta),0) AS bal
        FROM available_credit_ledger
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
    if is_enabled("link"):
        return RedirectResponse("/app/link/new", status_code=303)
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
        <input aria-label="URL destinazione" class="input" name="target_url" placeholder="https://..." required>

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
    require_csrf_or_same_origin(request)
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
                    FROM available_credit_ledger
                    WHERE user_id=%s AND credit_type='generic'
                    """,
                    (uid,),
                )
                bal = int((cur.fetchone() or {}).get("balance") or 0)
                if bal < 1:
                    conn.rollback()
                    return RedirectResponse("/app/billing?error=crediti_insufficienti", status_code=303)

            slug = new_slug()
            public_path = f"/d/{slug}"

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
    if is_enabled("link"):
        return RedirectResponse(f"/app/link/{int(qr_id)}", status_code=303)
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

    slug = str(r.get("slug") or "")
    absolute_url = _direct_public_url(request, slug)
    body = f"""
    <div class="h1" style="margin-top:14px">Il tuo QR Link</div>
    <div class="p">Il QR resta sempre lo stesso: puoi cambiare la destinazione quando vuoi, senza ristampare.</div>

    <div class="card" style="margin-top:14px;max-width:980px">
      <div class="h2">QR da stampare</div>
      <img src="/app/external/{int(qr_id)}/qr.png" alt="QR code del link" width="180" height="180" style="margin-top:10px;border:1px solid #e2e8f0;border-radius:12px">
      <div class="row" style="margin-top:14px">
        <a class="btn btn-primary" href="/app/external/{int(qr_id)}/qr.pdf">Scarica PDF per la stampa</a>
        <a class="btn" href="/app/external/{int(qr_id)}/qr.png" download>Scarica immagine PNG</a>
      </div>
      <div class="note" style="margin-top:12px">
        <b>Indirizzo del QR:</b> <a href="{esc(absolute_url)}" target="_blank" rel="noopener">{esc(absolute_url)}</a>
      </div>
    </div>

    <form class="card" method="post" action="/app/external/{int(qr_id)}/target" style="margin-top:14px;max-width:980px">
      {csrf_input(request)}
      <div class="h2">Destinazione</div>
      <label for="target-url" style="margin-top:10px">Dove porta il QR</label>
      <input id="target-url" class="input" name="target_url" value="{esc(target)}" placeholder="https://..." required>
      <div class="row" style="margin-top:12px">
        <button class="btn btn-primary" type="submit">Salva la nuova destinazione</button>
        <a class="btn" href="{esc(absolute_url)}" target="_blank" rel="noopener">Prova il QR</a>
      </div>
    </form>
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


def _valid_target(url: str) -> bool:
    url = (url or "").strip()
    if len(url) > 2000:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def _direct_public_url(request: Request, slug: str) -> str:
    base = str(getattr(request.app.state, "app_base_url", "") or "").rstrip("/")
    if not base:
        base = f"{request.url.scheme}://{request.headers.get('host', 'localhost:8000')}"
    return f"{base}/d/{slug}"


def _owned_external(cur, qr_id: int, user: dict) -> dict:
    cur.execute(
        "SELECT id, owner_user_id, slug, payload FROM qr_items WHERE id=%s AND qr_type='external' LIMIT 1",
        (int(qr_id),),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, "QR non trovato")
    if int(row["owner_user_id"]) != int(user["id"]) and (user.get("role") or "").lower() != "admin":
        raise HTTPException(403, "Forbidden")
    return row


@router.post("/app/external/{qr_id}/target")
def external_update_target(request: Request, qr_id: int, target_url: str = Form(...)):
    require_csrf_or_same_origin(request)
    u = require_any_role(request, ("winery", "studio", "admin"))
    target_url = (target_url or "").strip()
    if not _valid_target(target_url):
        return RedirectResponse(f"/app/external/{int(qr_id)}?err=Indirizzo%20non%20valido", status_code=303)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            _owned_external(cur, qr_id, u)
            cur.execute(
                "UPDATE qr_items SET payload=jsonb_build_object('url', %s::text), updated_at=%s WHERE id=%s",
                (target_url, now(), int(qr_id)),
            )
        conn.commit()
    return RedirectResponse(f"/app/external/{int(qr_id)}?msg=Destinazione%20aggiornata", status_code=303)


@router.get("/app/external/{qr_id}/qr.{fmt}")
def external_qr_file(request: Request, qr_id: int, fmt: str):
    from qrfacile_app.export_qr_ui import _qr_pdf_a4, _qr_png

    u = require_any_role(request, ("winery", "studio", "admin"))
    if fmt not in ("png", "pdf"):
        raise HTTPException(404, "Formato non disponibile")
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            row = _owned_external(cur, qr_id, u)
    url = _direct_public_url(request, str(row.get("slug") or ""))
    if fmt == "png":
        data, media, name = _qr_png(url, 30, 600), "image/png", f"qrfacile-link-{row['slug']}.png"
    else:
        data, media, name = _qr_pdf_a4(url, 30, 600), "application/pdf", f"qrfacile-link-{row['slug']}.pdf"
    return Response(data, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="{name}"',
        "Cache-Control": "no-store",
    })


_NOT_FOUND_HTML = (
    "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
    "<meta name='viewport' content='width=device-width,initial-scale=1'><title>QR non attivo</title>"
    "<link rel='stylesheet' href='/static/app.css'></head><body><main style='max-width:640px;margin:60px auto;padding:24px'>"
    "<div class='card'><h1 class='h1'>QR non attivo</h1><p>Questo QR non è collegato a nessun contenuto.</p></div>"
    "</main></body></html>"
)
