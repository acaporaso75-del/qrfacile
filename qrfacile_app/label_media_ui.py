import os
import time
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.auth import require_any_role
from qrfacile_app import ui
from qrfacile_app.media_labels import process_label_image

router = APIRouter()

UPLOAD_ROOT = "/opt/qrfacile/uploads"


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))
    except Exception:
        return "-"


def _load_label(cur, label_id: int) -> dict:
    cur.execute(
        """
      SELECT
        wl.id AS label_id,
        wl.winery_id,
        wl.wine_id,
        wl.qr_item_id,
        wl.label_type,
        wl.language,
        wl.title_override,
        wl.public_enabled,
        wl.updated_at,
        wl.label_img_original,
        wl.label_img_optimized,
        wl.label_img_thumb,
        qw.wine_name,
        qw.vintage,
        qw.lot AS wine_lot,
        w.name AS winery_name,
        w.owner_user_id
      FROM wine_labels wl
      JOIN qr_wines qw ON qw.id = wl.wine_id
      JOIN wineries w ON w.id = wl.winery_id
      WHERE wl.id=%s
      LIMIT 1
    """,
        (int(label_id),),
    )
    r = cur.fetchone()
    if not r:
        raise HTTPException(404, "Etichetta non trovata")
    return r


def _studio_acl(cur, studio_user_id: int, winery_id: int) -> dict | None:
    cur.execute(
        """
      SELECT can_view, can_edit, can_create
      FROM studio_clients
      WHERE studio_user_id=%s AND winery_id=%s
      LIMIT 1
    """,
        (int(studio_user_id), int(winery_id)),
    )
    return cur.fetchone()


def _can_view_edit_create(user: dict, label: dict, cur) -> tuple[bool, bool, bool]:
    role = (user.get("role") or "").lower().strip()

    if role == "admin":
        return True, True, True

    if role == "winery":
        if int(label["owner_user_id"]) == int(user["id"]):
            return True, True, True
        return False, False, False

    if role == "studio":
        acl = _studio_acl(cur, int(user["id"]), int(label["winery_id"]))
        if not acl:
            return False, False, False
        return bool(acl.get("can_view")), bool(acl.get("can_edit")), bool(
            acl.get("can_create")
        )

    return False, False, False


@router.get("/app/label/{label_id}/image", response_class=HTMLResponse)
def label_image_page(request: Request, label_id: int, msg: str = ""):
    user = require_any_role(request, ("winery", "studio", "admin"))

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label(cur, int(label_id))
            can_view, can_edit, _ = _can_view_edit_create(user, label, cur)

            if not can_view:
                raise HTTPException(403, "Forbidden")

    wine_id = int(label["wine_id"])
    winery_name = label.get("winery_name") or "-"
    wine_name = label.get("wine_name") or "-"
    lt = (label.get("label_type") or "").strip()
    lang = (label.get("language") or "").strip()

    thumb = (label.get("label_img_thumb") or "").strip()
    opt = (label.get("label_img_optimized") or "").strip()
    orig = (label.get("label_img_original") or "").strip()

    msg_html = f"<div class='note'><b>OK:</b> {ui.esc(msg)}</div>" if msg else ""

    def img_block(path: str, title: str) -> str:
        if not path:
            return f"<div class='card'><b>{ui.esc(title)}</b><div class='muted'>Nessun file</div></div>"
        return f"""
        <div class="card">
          <b>{ui.esc(title)}</b>
          <div style="margin-top:10px">
            <img src="/uploads/{ui.esc(path)}" style="width:100%;border-radius:16px;border:1px solid var(--line);background:#fff">
          </div>
          <div style="margin-top:10px;display:flex;gap:10px;flex-wrap:wrap">
            <a class="btn" href="/uploads/{ui.esc(path)}" target="_blank">Apri file</a>
          </div>
        </div>
        """

    if can_edit:
        upload_form = f"""
        <form class="card" method="post" action="/app/label/{int(label_id)}/image" enctype="multipart/form-data" style="max-width:860px">
          <div class="section-title">Carica immagine etichetta</div>
          <div class="p">Carica un file JPG, PNG o WEBP. Verranno generate versioni ottimizzate e thumbnail.</div>
          <input type="file" name="image" accept="image/jpeg,image/png,image/webp" required>
          <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap">
            <button class="btn btn-primary" type="submit">Carica</button>
            <a class="btn" href="/app/label/{int(label_id)}">Torna etichetta</a>
          </div>
        </form>
        """
    else:
        upload_form = "<div class='note'>Non hai permesso di modifica su questa cantina.</div>"

    html = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Immagine etichetta #{int(label_id)}</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>
<div class="container">

  <div class="topbar">
    <div class="brand">
      <div class="brand-dot"></div>
      <div>
        <div class="brand-title">QRFACILE</div>
        <div class="brand-sub">Etichetta · Media</div>
      </div>
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <a class="pill" href="/app/label/{int(label_id)}">← Etichetta</a>
      <a class="pill" href="/app/wine/{int(wine_id)}">Vino</a>
      <a class="pill" href="/app/labels/search">Ricerca avanzata</a>
      <a class="pill" href="/logout">Logout</a>
    </div>
  </div>

  <div class="h1">Etichetta #{int(label_id)} · {ui.esc(wine_name)}</div>
  <div class="p">{ui.esc(winery_name)} · tipo {ui.esc(lt)} · lang {ui.esc(lang)}</div>

  {msg_html}

  {upload_form}

  <div class="section" style="margin-top:16px">
    <div class="section-title">Anteprime</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
      {img_block(thumb, "Thumbnail")}
      {img_block(opt, "Ottimizzata")}
    </div>
    <div style="margin-top:12px">
      {img_block(orig, "Originale")}
    </div>
  </div>

</div>
</body>
</html>
"""
    return HTMLResponse(html)


@router.post("/app/label/{label_id}/image")
def label_image_upload(request: Request, label_id: int, image: UploadFile = File(...)):
    user = require_any_role(request, ("winery", "studio", "admin"))

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label(cur, int(label_id))
            can_view, can_edit, _ = _can_view_edit_create(user, label, cur)

            if not can_view:
                raise HTTPException(403, "Forbidden")
            if not can_edit:
                raise HTTPException(403, "Forbidden")

            winery_id = int(label["winery_id"])

            result = process_label_image(
                image,
                winery_id=winery_id,
                label_id=int(label_id),
            )

            ts = int(time.time())

            cur.execute(
                """
                UPDATE wine_labels
                SET
                  label_img_original=%s,
                  label_img_optimized=%s,
                  label_img_thumb=%s,
                  updated_at=%s
                WHERE id=%s
                """,
                (
                    result.get("original"),
                    result.get("optimized"),
                    result.get("thumb"),
                    ts,
                    int(label_id),
                ),
            )
            conn.commit()

    return RedirectResponse(
        f"/app/label/{int(label_id)}/image?msg=Caricato",
        status_code=303,
    )

