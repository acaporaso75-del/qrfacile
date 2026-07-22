import os
import io
import re
import smtplib
from email.message import EmailMessage

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app import ui

import qrcode
from PIL import Image
try:
    import segno
except Exception:
    segno = None

router = APIRouter()


def _sanitize(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:120] if s else "file"


def _qr_url(request: Request, slug: str) -> str:
    base = request.app.state.app_base_url
    return f"{base}/r/{slug}"


def _qr_png(url: str) -> bytes:
    if segno:
        qr = segno.make(url, micro=False)
        bio = io.BytesIO()
        qr.save(bio, kind="png", scale=10, border=4)
        return bio.getvalue()
    img = qrcode.make(url)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def _qr_jpg(url: str) -> bytes:
    png = _qr_png(url)
    img = Image.open(io.BytesIO(png))
    if img.mode != "RGB":
        img = img.convert("RGB")
    bio = io.BytesIO()
    img.save(bio, format="JPEG", quality=92, optimize=True, progressive=True)
    return bio.getvalue()


def _qr_svg(url: str) -> bytes:
    if not segno:
        raise HTTPException(501, "SVG non disponibile: installa segno")
    qr = segno.make(url, micro=False)
    bio = io.BytesIO()
    qr.save(bio, kind="svg", border=4, xmldecl=True)
    return bio.getvalue()


def _smtp_cfg():
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "465"))
    user = os.getenv("SMTP_USER", "")
    pwd = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("SMTP_FROM", "") or user
    if not host or not user or not pwd or not from_email:
        raise HTTPException(500, "SMTP non configurato in /opt/qrfacile/.env")
    return host, port, user, pwd, from_email


def _send_mail(to_email: str, subject: str, body: str, filename: str, data: bytes, mime: str):
    host, port, user, pwd, from_email = _smtp_cfg()

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    maintype, subtype = mime.split("/", 1)
    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    if port == 465:
        with smtplib.SMTP_SSL(host, port) as s:
            s.login(user, pwd)
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)


def _check_access(cur, user: dict, slug: str) -> dict:
    role = (user.get("role") or "").lower()

    cur.execute("""
      SELECT wl.id AS label_id, wl.winery_id, wl.label_type, wl.language,
             COALESCE(wl.lot_override,'') AS lot_override,
             wl.created_by_user_id,
             qw.wine_name, qw.vintage,
             w.name AS winery_name,
             qi.slug
      FROM wine_labels wl
      JOIN qr_items qi ON qi.id=wl.qr_item_id
      JOIN qr_wines qw ON qw.id=wl.wine_id
      JOIN wineries w ON w.id=wl.winery_id
      WHERE qi.slug=%s
      LIMIT 1
    """, (slug,))
    r = cur.fetchone()
    if not r:
        raise HTTPException(404, "Etichetta non trovata")

    if role == "admin":
        return r

    if role == "winery":
        cur.execute("SELECT id FROM wineries WHERE owner_user_id=%s", (int(user["id"]),))
        wrow = cur.fetchone()
        if not wrow or int(wrow["id"]) != int(r["winery_id"]):
            raise HTTPException(403, "Non autorizzato")
        return r

    if role == "studio":
        if r.get("created_by_user_id") and int(r["created_by_user_id"]) == int(user["id"]):
            return r
        cur.execute("""
          SELECT 1 FROM wine_labels_acl
          WHERE wine_label_id=%s AND studio_user_id=%s AND can_view=TRUE
          LIMIT 1
        """, (int(r["label_id"]), int(user["id"])))
        if cur.fetchone():
            return r
        raise HTTPException(403, "Non autorizzato")

    raise HTTPException(403, "Non autorizzato")


@router.get("/app/print/send", response_class=HTMLResponse)
def send_form(request: Request, slug: str = "", back: str = "/app/dashboard"):
    user, conn = require_any_role(request, ["winery", "studio", "admin"])
    conn.close()

    header = ui.header(
        "Invio tipografia",
        "Invia il QR alla tipografia come file allegato (non l’etichetta).",
        ui.nav_buttons([(back, "Indietro", "ghost"), ("/app/dashboard", "Dashboard", "ghost")])
    )

    if not slug:
        return ui.layout("Invio tipografia", header + ui.card("", "<div class='muted'>Apri questa pagina dalla ricerca etichette (tasto “Stampa”).</div>"))

    body = header + f"""
<div class="card">
  <form method="post" action="/app/print/send">
    <input type="hidden" name="back" value="{back}">
    <label>Slug</label>
    <input name="slug" value="{slug}" readonly>

    <div class="grid2">
      <div>
        <label>Formato</label>
        <select name="fmt">
          <option value="png">PNG</option>
          <option value="jpg">JPG</option>
          <option value="svg">SVG (vettoriale)</option>
        </select>
      </div>
      <div>
        <label>Email tipografia</label>
        <input name="to_email" type="email" required placeholder="tipografia@...">
      </div>
    </div>

    <label>Note (opzionale)</label>
    <input name="note" placeholder="es. stampa 10k pezzi, back IT lotto L24-001">

    <div style="margin-top:14px">
      <button class="btn" type="submit">Invia</button>
    </div>
  </form>
</div>
"""
    return ui.layout("Invio tipografia", body)


@router.post("/app/print/send")
def send_post(
    request: Request,
    slug: str = Form(...),
    fmt: str = Form("png"),
    to_email: str = Form(...),
    note: str = Form(""),
    back: str = Form("/app/dashboard"),
):
    user, conn = require_any_role(request, ["winery", "studio", "admin"])
    try:
        fmt = (fmt or "png").lower().strip()
        if fmt not in ("png", "jpg", "svg"):
            raise HTTPException(400, "Formato non valido")

        with conn.cursor(row_factory=dict_row) as cur:
            info = _check_access(cur, user, slug)

        url = _qr_url(request, slug)

        if fmt == "png":
            data = _qr_png(url); mime = "image/png"
        elif fmt == "jpg":
            data = _qr_jpg(url); mime = "image/jpeg"
        else:
            data = _qr_svg(url); mime = "image/svg+xml"

        winery = _sanitize(info["winery_name"])
        wine = _sanitize(info["wine_name"])
        vintage = _sanitize(info.get("vintage", "") or "")
        lot = _sanitize(info.get("lot_override", "") or "")
        lt = _sanitize(info.get("label_type", "label"))
        lang = _sanitize(info.get("language", "it"))

        filename = _sanitize(f"{winery}_{wine}_{vintage}_{lot}_{lt}_{lang}_{slug}.{fmt}")

        subject = f"QRFACILE — QR per stampa ({wine})"
        body = f"""In allegato il QR richiesto.

Cantina: {info['winery_name']}
Vino: {info['wine_name']}
Annata: {info.get('vintage','')}
Lotto: {info.get('lot_override','')}
Tipo: {info.get('label_type','')}
Lingua: {info.get('language','')}
Slug: {slug}

Note: {note}
"""

        _send_mail(to_email, subject, body, filename, data, mime)
        return RedirectResponse(back, status_code=303)
    finally:
        conn.close()
