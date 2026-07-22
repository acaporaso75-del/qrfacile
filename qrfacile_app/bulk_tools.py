import io
import json
import re
import time
from typing import List

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.util import now_epoch, new_slug

# QR generation (PNG for PDF)
import qrcode
from PIL import Image
try:
    import segno
except Exception:
    segno = None

# PDF
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

router = APIRouter()


# ----------------------------
# Helpers
# ----------------------------
def _qr_url(request: Request, slug: str) -> str:
    base = request.app.state.app_base_url
    return f"{base}/e/{slug}"


def _qr_png_bytes(url: str) -> bytes:
    if segno:
        qr = segno.make(url, micro=False)
        bio = io.BytesIO()
        qr.save(bio, kind="png", scale=10, border=4)
        return bio.getvalue()
    img = qrcode.make(url)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def _sanitize(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:120] if s else "file"


def _allowed_wineries_macro(cur, user: dict) -> List[int]:
    role = (user.get("role") or "").lower()
    if role == "admin":
        cur.execute("SELECT id FROM wineries ORDER BY id")
        return [int(r["id"]) for r in (cur.fetchall() or [])]
    if role == "studio":
        cur.execute("""
          SELECT winery_id
          FROM studio_clients
          WHERE studio_user_id=%s AND can_view=TRUE
        """, (int(user["id"]),))
        return [int(r["winery_id"]) for r in (cur.fetchall() or [])]
    # winery owner
    cur.execute("SELECT id FROM wineries WHERE owner_user_id=%s", (int(user["id"]),))
    r = cur.fetchone()
    return [int(r["id"])] if r else []


def _studio_acl_where(studio_user_id: int) -> str:
    # micro ACL: studio can see label if created_by_user_id == studio OR ACL table can_view
    return f"""(
      wl.created_by_user_id = {int(studio_user_id)}
      OR EXISTS (
        SELECT 1
        FROM wine_labels_acl a
        WHERE a.wine_label_id = wl.id
          AND a.studio_user_id = {int(studio_user_id)}
          AND a.can_view = TRUE
      )
    )"""


def _label_visible_to_studio(cur, label_id: int, studio_user_id: int) -> dict:
    """
    Studio sees label if creator OR ACL micro can_view.
    Returns label row + wine_name/vintage + winery_name + slug.
    """
    cur.execute("""
      SELECT wl.*, qi.slug, qw.wine_name, qw.vintage, w.name AS winery_name
      FROM wine_labels wl
      JOIN qr_items qi ON qi.id=wl.qr_item_id
      JOIN qr_wines qw ON qw.id=wl.wine_id
      JOIN wineries w ON w.id=wl.winery_id
      WHERE wl.id=%s
      LIMIT 1
    """, (int(label_id),))
    lb = cur.fetchone()
    if not lb:
        raise HTTPException(404, "Etichetta non trovata")

    if lb.get("created_by_user_id") and int(lb["created_by_user_id"]) == int(studio_user_id):
        return lb

    cur.execute("""
      SELECT 1 FROM wine_labels_acl a
      WHERE a.wine_label_id=%s AND a.studio_user_id=%s AND a.can_view=TRUE
      LIMIT 1
    """, (int(label_id), int(studio_user_id)))
    if cur.fetchone():
        return lb

    raise HTTPException(403, "Non autorizzato")


def _label_owner_check(cur, user: dict, label_id: int) -> dict:
    """
    Winery/admin can manage label if belongs to winery.
    Returns label row + wine_name/vintage + winery_name + slug.
    """
    role = (user.get("role") or "").lower()
    cur.execute("""
      SELECT wl.*, qi.slug, qw.wine_name, qw.vintage, w.name AS winery_name
      FROM wine_labels wl
      JOIN qr_items qi ON qi.id=wl.qr_item_id
      JOIN qr_wines qw ON qw.id=wl.wine_id
      JOIN wineries w ON w.id=wl.winery_id
      WHERE wl.id=%s
      LIMIT 1
    """, (int(label_id),))
    lb = cur.fetchone()
    if not lb:
        raise HTTPException(404, "Etichetta non trovata")

    if role == "admin":
        return lb

    if role != "winery":
        raise HTTPException(403, "Non autorizzato")

    cur.execute("SELECT id FROM wineries WHERE owner_user_id=%s", (int(user["id"]),))
    w = cur.fetchone()
    if not w or int(w["id"]) != int(lb["winery_id"]):
        raise HTTPException(403, "Non autorizzato")

    return lb


def _parse_lots(text: str) -> List[str]:
    """
    One lot per line. Trims empties. Max 500.
    """
    lots = []
    for line in (text or "").splitlines():
        s = line.strip()
        if s:
            lots.append(s)
    return lots[:500]


# ----------------------------
# Bulk clone (UI)
# ----------------------------
@router.get("/app/bulk/clone", response_class=HTMLResponse)
def bulk_clone_form(request: Request, label_id: int = 0):
    require_any_role(request, ["winery", "studio", "admin"])
    return HTMLResponse(f"""
<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bulk clone</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>
<div class="container">
  <div class="h1">Bulk clone etichette</div>
  <div class="p">Replica una etichetta N volte cambiando lotto (1 per riga). Crea nuovi QR.</div>

  <form class="card" method="post" action="/app/bulk/clone" style="max-width:760px">
    <label>ID etichetta sorgente</label>
    <input class="input" name="label_id" value="{label_id or ''}" required>

    <div style="margin-top:12px">
      <label>Lista lotti (uno per riga)</label>
      <textarea class="input" name="lots" rows="10" style="min-height:220px" placeholder="L24-001&#10;L24-002&#10;L24-003"></textarea>
    </div>

    <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap">
      <button class="btn btn-primary" type="submit">Clona</button>
      <a class="btn" href="/app/labels/search">Ricerca</a>
      <a class="btn" href="/app/dashboard">Dashboard</a>
    </div>

    <div class="note" style="margin-top:12px">
      Studio: serve permesso <b>create</b> sulla cantina. Cantina: puoi clonare solo le tue etichette.
    </div>
  </form>
</div>
</body>
</html>
""")


@router.post("/app/bulk/clone")
def bulk_clone_post(request: Request, label_id: int = Form(...), lots: str = Form("")):
    user = require_any_role(request, ["winery", "studio", "admin"])
    ts = now_epoch()
    lot_list = _parse_lots(lots)
    if not lot_list:
        raise HTTPException(400, "Inserisci almeno un lotto")

    created = 0

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            role = (user.get("role") or "").lower()

            # load source label with permission rules
            if role == "studio":
                src = _label_visible_to_studio(cur, int(label_id), int(user["id"]))
                # ENFORCEMENT: studio must have create on winery_id
                require_any_role(request, ["studio", "admin"], winery_id=int(src["winery_id"]), need="create")
            else:
                src = _label_owner_check(cur, user, int(label_id))

            for lot in lot_list:
                # create new qr_items
                slug = new_slug()
                public_path = f"/e/{slug}"
                payload = json.dumps(
                    {"type": "wine_label", "label_type": src["label_type"], "lang": src["language"]},
                    ensure_ascii=False
                )

                # owner_user_id: cantina owner_user_id (NOT studio id)
                cur.execute("SELECT owner_user_id FROM wineries WHERE id=%s", (int(src["winery_id"]),))
                ow = cur.fetchone()
                owner_user_id = int(ow["owner_user_id"]) if ow and ow.get("owner_user_id") else None
                if not owner_user_id:
                    raise HTTPException(500, "Owner cantina non trovato")

                cur.execute("""
                  INSERT INTO qr_items(owner_user_id, winery_id, qr_type, status, slug, title, public_path, has_back, payload, created_at, updated_at)
                  VALUES (%s,%s,'cantina','bozza',%s,%s,%s,1,%s::jsonb,%s,%s)
                  RETURNING id
                """, (
                    owner_user_id,
                    int(src["winery_id"]),
                    slug,
                    f"{src['wine_name']} ({src['label_type']})",
                    public_path,
                    payload,
                    ts,
                    ts
                ))
                qr_item_id = int(cur.fetchone()["id"])

                # clone wine_labels
                cur.execute("""
                  INSERT INTO wine_labels(
                    wine_id, winery_id, qr_item_id,
                    label_type, language, lot_override, title_override,
                    active, public_enabled, published_at,
                    created_at, updated_at,
                    created_by_user_id
                  )
                  VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE,FALSE,NULL,%s,%s,%s)
                  RETURNING id
                """, (
                    int(src["wine_id"]),
                    int(src["winery_id"]),
                    qr_item_id,
                    src["label_type"],
                    src["language"],
                    lot,
                    src.get("title_override"),
                    ts, ts,
                    int(user["id"]) if role == "studio" else None
                ))
                _ = cur.fetchone()["id"]
                created += 1

        conn.commit()

    return HTMLResponse(f"<h2>OK</h2><p>Clonate: <b>{created}</b></p><p><a href='/app/labels/search'>Torna alla ricerca</a></p>")


# ----------------------------
# PDF multipagina (pack tipografia)
# ----------------------------
@router.get("/app/labels/printpack.pdf")
def printpack_pdf(
    request: Request,
    q: str = "",
    lot: str = "",
    label_type: str = "",
    language: str = "",
    winery_id: int = 0,
    limit: int = 200,
):
    """
    Genera PDF multipagina con griglia 3x4 (12 QR per pagina) + titolo su ogni cella.
    Rispetta ACL macro e micro (studio).
    """
    user = require_any_role(request, ["winery", "studio", "admin"])

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            role = (user.get("role") or "").lower()
            allowed = _allowed_wineries_macro(cur, user)
            if not allowed:
                raise HTTPException(403, "Nessuna cantina associata")

            if winery_id and int(winery_id) in allowed:
                allowed = [int(winery_id)]

            limit = max(1, min(int(limit), 1000))

            cond = ["wl.winery_id = ANY(%s)"]
            params = [allowed]

            if q:
                cond.append("LOWER(qw.wine_name) LIKE %s")
                params.append(f"%{q.lower()}%")
            if lot:
                cond.append("(COALESCE(wl.lot_override,'') ILIKE %s OR COALESCE(qw.lot,'') ILIKE %s)")
                params.extend([f"%{lot}%", f"%{lot}%"])
            if label_type:
                cond.append("wl.label_type=%s")
                params.append(label_type)
            if language:
                cond.append("wl.language=%s")
                params.append(language)

            if role == "studio":
                cond.append(_studio_acl_where(int(user["id"])))

            where = " AND ".join(cond)

            cur.execute(f"""
              SELECT wl.label_type, wl.language, wl.lot_override,
                     qw.wine_name, qw.vintage, COALESCE(qw.lot,'') AS wine_lot,
                     w.name AS winery_name,
                     qi.slug
              FROM wine_labels wl
              JOIN qr_wines qw ON qw.id=wl.wine_id
              JOIN wineries w ON w.id=wl.winery_id
              JOIN qr_items qi ON qi.id=wl.qr_item_id
              WHERE {where}
              ORDER BY wl.id DESC
              LIMIT %s
            """, params + [limit])
            rows = cur.fetchall() or []

    # Build PDF
    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    cols, rows_per_page = 3, 4
    cell_w = (W - 2 * 12 * mm) / cols
    cell_h = (H - 2 * 12 * mm) / rows_per_page
    margin_x = 12 * mm
    margin_y = 12 * mm

    def draw_cell(ix, iy, title, qr_png):
        x = margin_x + ix * cell_w
        y = H - margin_y - (iy + 1) * cell_h
        c.setFont("Helvetica", 8)
        c.drawString(x + 3, y + cell_h - 10, title[:55])
        img = ImageReader(io.BytesIO(qr_png))
        size = min(cell_w, cell_h) - 18
        c.drawImage(img, x + (cell_w - size) / 2, y + 8, width=size, height=size, preserveAspectRatio=True, mask='auto')

    for idx, r in enumerate(rows):
        page_i = idx // (cols * rows_per_page)
        pos = idx % (cols * rows_per_page)
        ix = pos % cols
        iy = pos // cols
        if pos == 0 and idx > 0:
            c.showPage()

        slug = r["slug"]
        url = _qr_url(request, slug)
        qr_png = _qr_png_bytes(url)
        lot_txt = (r.get("lot_override") or r.get("wine_lot") or "").strip()
        title = f"{r.get('winery_name','')} · {r.get('wine_name','')} · {lot_txt}"
        draw_cell(ix, iy, title, qr_png)

    c.showPage()
    c.save()
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="qrfacile_printpack.pdf"'},
    )
