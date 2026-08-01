import os
import io
import time

from PIL import Image, ImageFile
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.ui_shell import page, top_actions, pill, esc
from qrfacile_app.guided_flow import render_guided_stepper

router = APIRouter()

UPLOADS_DIR = os.getenv("UPLOADS_DIR", os.path.join(os.getenv("APP_ROOT", "/opt/qrfacile"), "uploads"))
UPLOAD_BASE = os.path.join(UPLOADS_DIR, "wine_assets")

# Hardening upload
MAX_UPLOAD_BYTES = 5 * 1024 * 1024        # 5MB
MAX_IMAGE_PIXELS = 40_000_000             # 40 MP anti-decompression-bomb
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp"}

# Non accettare immagini tronche
ImageFile.LOAD_TRUNCATED_IMAGES = False


def now() -> int:
    return int(time.time())


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _safe_ext(filename: str) -> str:
    fn = (filename or "").lower().strip()

    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if fn.endswith(ext):
            return ext

    return ".jpg"


def _ext_from_format(fmt: str) -> str:
    fmt = (fmt or "").upper().strip()

    if fmt == "PNG":
        return ".png"

    if fmt == "WEBP":
        return ".webp"

    return ".jpg"


def _read_limited(upload: UploadFile, max_bytes: int) -> bytes | None:
    """
    Legge al massimo max_bytes+1 bytes.
    Se supera max_bytes => ritorna None.
    """
    try:
        data = upload.file.read(max_bytes + 1)
    except Exception:
        return b""

    if not data:
        return b""

    if len(data) > max_bytes:
        return None

    return data


def _validate_image_bytes(data: bytes) -> str | None:
    """
    Verifica reale che sia un'immagine valida e ritorna formato: JPEG/PNG/WEBP.
    """
    if not data or len(data) < 64:
        return None

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

    try:
        im = Image.open(io.BytesIO(data))
        fmt = (im.format or "").upper()
        im.verify()

        if fmt not in ("JPEG", "PNG", "WEBP"):
            return None

        im2 = Image.open(io.BytesIO(data))
        _ = im2.size
        im2.load()

        return fmt

    except Image.DecompressionBombError:
        return None
    except Exception:
        return None


def _save_images(wine_id: int, kind: str, data: bytes, ext: str) -> dict:
    wine_dir = os.path.join(UPLOAD_BASE, str(wine_id), kind)
    _ensure_dir(wine_dir)

    orig_name = f"original{ext}"
    orig_path = os.path.join(wine_dir, orig_name)

    with open(orig_path, "wb") as f:
        f.write(data)

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    img = Image.open(io.BytesIO(data))
    img.load()

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg

    w, h = img.size
    max_side = max(w, h)

    if max_side > 2000:
        scale = 2000 / max_side
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))

    opt_path = os.path.join(wine_dir, "optimized.jpg")
    img.save(opt_path, format="JPEG", quality=88, optimize=True, progressive=True)

    thumb = img.copy()
    thumb.thumbnail((640, 640))
    thumb_path = os.path.join(wine_dir, "thumb.webp")
    thumb.save(thumb_path, format="WEBP", quality=82, method=6)

    return {
        "img_original": f"wine_assets/{wine_id}/{kind}/{orig_name}",
        "img_optimized": f"wine_assets/{wine_id}/{kind}/optimized.jpg",
        "img_thumb": f"wine_assets/{wine_id}/{kind}/thumb.webp",
    }


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


def _wine(cur, wine_id: int) -> dict:
    cur.execute(
        """
        SELECT
          qw.id AS wine_id,
          qw.winery_id,
          qw.wine_name,
          qw.lot,
          qw.vintage,
          w.name AS winery_name
        FROM qr_wines qw
        JOIN wineries w ON w.id = qw.winery_id
        WHERE qw.id=%s
        LIMIT 1
        """,
        (int(wine_id),),
    )
    r = cur.fetchone()

    if not r:
        raise HTTPException(404, "Vino non trovato")

    return r


def _asset(cur, wine_id: int, kind: str) -> dict:
    cur.execute(
        """
        SELECT id, img_original, img_optimized, img_thumb
        FROM wine_assets
        WHERE wine_id=%s AND kind=%s
        LIMIT 1
        """,
        (int(wine_id), kind),
    )
    return cur.fetchone() or {}


def _image_card(wine_id: int, kind: str, asset: dict) -> str:
    title = "Fronte" if kind == "front" else "Retro"
    thumb = (asset.get("img_thumb") or "").strip()
    original = (asset.get("img_original") or "").strip()
    optimized = (asset.get("img_optimized") or "").strip()

    thumb_readable = bool(thumb and os.path.isfile(os.path.join(UPLOADS_DIR, thumb)) and os.access(os.path.join(UPLOADS_DIR, thumb), os.R_OK))
    if thumb_readable:
        preview = f"""
        <div class="imagesPreviewBox">
          <img src="/uploads/{esc(thumb)}" alt="{esc(title)}">
        </div>
        """
        status = """
        <span class="pill pill-green">Immagine caricata</span>
        """
    else:
        preview = f"""
        <div class="imagesPlaceholder">
          <div class="imagesPlaceholderIcon">🖼️</div>
          <b>{esc(title)}</b>
          <span>Nessuna immagine caricata</span>
        </div>
        """
        status = """
        <span class="pill pill-muted">Da caricare</span>
        """

    tech_rows = ""
    if original or optimized or thumb:
        tech_rows = f"""
        <div class="imagesTech">
          <div><span>Originale</span><b>{esc(original or "-")}</b></div>
          <div><span>Ottimizzata</span><b>{esc(optimized or "-")}</b></div>
          <div><span>Thumbnail</span><b>{esc(thumb or "-")}</b></div>
        </div>
        """

    delete_form = ""
    if thumb_readable:
        delete_form = f"""
        <form method="post" action="/app/wine/{int(wine_id)}/images/delete"
              onsubmit="return confirm('Eliminare immagine {esc(title)}?');">
          <input type="hidden" name="kind" value="{esc(kind)}">
          <button class="btn btn-danger-soft" type="submit">Elimina</button>
        </form>
        """

    return f"""
    <article class="card imagesCard">
      <div class="imagesCardHead">
        <div>
          <div class="imagesSmallLabel">Immagine etichetta</div>
          <div class="h2">{esc(title)}</div>
        </div>
        {status}
      </div>

      {preview}

      <form method="post"
            action="/app/wine/{int(wine_id)}/images/upload"
            enctype="multipart/form-data"
            class="imagesUploadForm">
        <input type="hidden" name="kind" value="{esc(kind)}">

        <div>
          <label>Carica nuova immagine</label>
          <input class="input" type="file" name="image" accept="image/png,image/jpeg,image/webp" required>
        </div>

        <button class="btn btn-primary" type="submit">Upload</button>
      </form>

      <div class="imagesCardActions">
        {delete_form}
      </div>

      {tech_rows}
    </article>
    """


@router.get("/app/wine/{wine_id}/images", response_class=HTMLResponse)
def images_page(request: Request, wine_id: int, msg: str = ""):
    user = require_any_role(request, ("winery", "studio", "admin"))
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            balances = _balances(cur, uid)
            w = _wine(cur, int(wine_id))

    require_any_role(
        request,
        ("winery", "studio", "admin"),
        winery_id=int(w["winery_id"]),
        need="view",
    )

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            front = _asset(cur, int(wine_id), "front")
            back = _asset(cur, int(wine_id), "back")

    actions = (
        pill(f"wine: {balances.get('wine', 0)}", "green") + " " +
        pill(f"generic: {balances.get('generic', 0)}") + " " +
        top_actions(
            (f"/app/wine/{int(wine_id)}", "Overview"),
            ("/app/dashboard", "Dashboard"),
            ("/logout", "Logout"),
        )
    )

    msg_html = ""
    if msg:
        msg_html = f"""
        <div class="note note-ok" style="margin-top:18px">
          <b>OK:</b> {esc(msg)}
        </div>
        """

    wine_name = esc(w.get("wine_name") or "")
    winery_name = esc(w.get("winery_name") or "")
    lot = esc(w.get("lot") or "")
    vintage = esc(str(w.get("vintage") or "").strip())

    vintage_html = f"<span>Annata <b>{vintage}</b></span>" if vintage else ""
    lot_html = f"<span>Lotto <b>{lot}</b></span>" if lot else ""

    body = f"""
    <section class="imagesWrap">
      <div class="imagesHero">
        <div>
          <div class="imagesEyebrow">Immagini etichetta</div>

          <div class="h1">Fronte e retro</div>

          <div class="p">
            Carica le immagini dell’etichetta per il lotto <b>{wine_name}</b>
            della cantina <b>{winery_name}</b>.
          </div>

          <div class="imagesMeta">
            {vintage_html}
            {lot_html}
          </div>

          {msg_html}
        </div>

        <div class="imagesHeroCard">
          <div class="imagesHeroCardTitle">Regole upload</div>

          <div class="imagesRules">
            <div><b>JPG / PNG / WebP</b><span>Formati accettati</span></div>
            <div><b>Max 5MB</b><span>Limite per file</span></div>
            <div><b>Anti-bomb</b><span>Controllo immagine reale</span></div>
          </div>
        </div>
      </div>

      {render_guided_stepper(int(wine_id), "images", {"wine"})}

      <div class="imagesTabs">
        <a class="imagesTab" href="/app/wine/{int(wine_id)}">Overview</a>
        <a class="imagesTab active" href="/app/wine/{int(wine_id)}/images">Immagini</a>
        <a class="imagesTab" href="/app/wine/{int(wine_id)}/compliance">Compliance</a>
        <a class="imagesTab" href="/app/wine/{int(wine_id)}/export">Export</a>
      </div>

      <div class="imagesFlow">
        <a class="active" href="/app/wine/{int(wine_id)}/images">
          <span>1</span>
          <b>Immagini</b>
          <small>Carica fronte e retro</small>
        </a>

        <a href="/app/wine/{int(wine_id)}/compliance">
          <span>2</span>
          <b>Compliance</b>
          <small>Compila dati obbligatori</small>
        </a>

        <a href="/app/wine/{int(wine_id)}/export">
          <span>3</span>
          <b>Export</b>
          <small>Scarica QR per stampa</small>
        </a>
      </div>

      <div class="imagesGrid">
        {_image_card(int(wine_id), "front", front)}
        {_image_card(int(wine_id), "back", back)}
      </div>

      <div class="note" style="margin-top:18px">
        I file vengono salvati in versione originale, ottimizzata e thumbnail.
        Le immagini non valide, troppo grandi o non supportate vengono rifiutate.
      </div>

      <div class="complianceActions" style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px">
        <a class="btn" href="/app/wine/{int(wine_id)}">Indietro</a>
        <a class="btn" href="/app/wine/{int(wine_id)}/images">Salva</a>
        <a class="btn btn-primary" href="/app/wine/{int(wine_id)}/compliance#ingredienti">Salva e continua</a>
      </div>

      <style>
        .imagesWrap {{
          max-width:1180px;
          margin:0 auto;
        }}

        .imagesHero {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:28px;
          overflow:hidden;
          box-shadow:0 24px 80px rgba(2,8,23,.08);
          background:
            radial-gradient(circle at 8% 12%, rgba(191,245,230,.58), transparent 34%),
            radial-gradient(circle at 92% 8%, rgba(207,232,255,.58), transparent 34%),
            linear-gradient(135deg,rgba(255,255,255,.96),rgba(248,252,250,.92));
          padding:30px;
          display:grid;
          grid-template-columns:minmax(0,1.35fr) 320px;
          gap:24px;
          align-items:end;
        }}

        .imagesEyebrow {{
          display:inline-flex;
          padding:7px 12px;
          border-radius:999px;
          background:rgba(20,184,166,.10);
          color:#0f766e;
          font-size:12px;
          font-weight:950;
          letter-spacing:.08em;
          text-transform:uppercase;
        }}

        .imagesMeta {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:16px;
        }}

        .imagesMeta span {{
          display:inline-flex;
          padding:8px 11px;
          border-radius:999px;
          background:rgba(255,255,255,.72);
          border:1px solid rgba(2,8,23,.07);
          color:#475569;
          font-size:12px;
          font-weight:850;
        }}

        .imagesMeta b {{
          color:#0f172a;
          margin-left:4px;
        }}

        .imagesHeroCard {{
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.72);
          border-radius:24px;
          padding:18px;
          box-shadow:0 18px 45px rgba(2,8,23,.06);
        }}

        .imagesHeroCardTitle {{
          color:#64748b;
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.08em;
        }}

        .imagesRules {{
          display:grid;
          gap:10px;
          margin-top:14px;
        }}

        .imagesRules div {{
          border:1px solid rgba(2,8,23,.07);
          border-radius:17px;
          padding:12px;
          background:rgba(255,255,255,.68);
        }}

        .imagesRules b {{
          display:block;
          font-size:14px;
          font-weight:950;
        }}

        .imagesRules span {{
          display:block;
          margin-top:3px;
          color:#64748b;
          font-size:12px;
          font-weight:750;
        }}

        .imagesTabs {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:18px;
        }}

        .imagesTab {{
          display:inline-flex;
          align-items:center;
          justify-content:center;
          padding:12px 16px;
          border-radius:18px;
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.76);
          font-weight:950;
          box-shadow:0 12px 30px rgba(2,8,23,.04);
        }}

        .imagesTab.active {{
          background:linear-gradient(135deg,rgba(191,245,230,.95),rgba(207,232,255,.88));
          border-color:rgba(20,184,166,.18);
        }}

        .imagesFlow {{
          display:grid;
          grid-template-columns:repeat(3,minmax(0,1fr));
          gap:14px;
          margin-top:18px;
        }}

        .imagesFlow a {{
          display:flex;
          gap:12px;
          align-items:flex-start;
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          padding:16px;
          background:rgba(255,255,255,.78);
          box-shadow:0 12px 30px rgba(2,8,23,.04);
        }}

        .imagesFlow a.active {{
          background:linear-gradient(135deg,rgba(191,245,230,.78),rgba(207,232,255,.62));
          border-color:rgba(20,184,166,.18);
        }}

        .imagesFlow span {{
          width:34px;
          height:34px;
          border-radius:13px;
          display:flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.92),rgba(207,232,255,.92));
          font-weight:950;
          flex:0 0 auto;
        }}

        .imagesFlow b {{
          display:block;
          font-size:15px;
          font-weight:950;
        }}

        .imagesFlow small {{
          display:block;
          margin-top:3px;
          color:#64748b;
          font-size:12px;
          font-weight:750;
          line-height:1.35;
        }}

        .imagesGrid {{
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:18px;
          margin-top:18px;
        }}

        .imagesCard {{
          padding:22px;
        }}

        .imagesCardHead {{
          display:flex;
          justify-content:space-between;
          gap:14px;
          align-items:flex-start;
          margin-bottom:16px;
        }}

        .imagesSmallLabel {{
          color:#64748b;
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.08em;
        }}

        .imagesPreviewBox {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          overflow:hidden;
          background:#fff;
        }}

        .imagesPreviewBox img {{
          width:100%;
          height:340px;
          object-fit:cover;
          display:block;
        }}

        .imagesPlaceholder {{
          min-height:300px;
          border:1px dashed rgba(2,8,23,.16);
          border-radius:22px;
          background:
            radial-gradient(circle at 20% 10%, rgba(191,245,230,.45), transparent 50%),
            rgba(255,255,255,.70);
          display:flex;
          align-items:center;
          justify-content:center;
          flex-direction:column;
          text-align:center;
          padding:24px;
        }}

        .imagesPlaceholderIcon {{
          width:58px;
          height:58px;
          border-radius:20px;
          display:flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.85),rgba(207,232,255,.85));
          font-size:26px;
          margin-bottom:12px;
        }}

        .imagesPlaceholder b {{
          font-size:17px;
          font-weight:950;
        }}

        .imagesPlaceholder span {{
          color:#64748b;
          font-size:13px;
          font-weight:750;
          margin-top:4px;
        }}

        .imagesUploadForm {{
          margin-top:16px;
          display:grid;
          grid-template-columns:minmax(0,1fr) auto;
          gap:12px;
          align-items:end;
        }}

        .imagesCardActions {{
          margin-top:12px;
          display:flex;
          gap:10px;
          flex-wrap:wrap;
        }}

        .imagesTech {{
          margin-top:16px;
          display:grid;
          gap:8px;
          padding:12px;
          border:1px solid rgba(2,8,23,.07);
          border-radius:18px;
          background:rgba(255,255,255,.65);
        }}

        .imagesTech div {{
          min-width:0;
        }}

        .imagesTech span {{
          display:block;
          color:#64748b;
          font-size:11px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.06em;
        }}

        .imagesTech b {{
          display:block;
          margin-top:3px;
          font-size:12px;
          font-weight:800;
          word-break:break-word;
        }}

        @media(max-width:980px) {{
          .imagesHero,
          .imagesGrid {{
            grid-template-columns:1fr;
          }}

          .imagesFlow {{
            grid-template-columns:1fr;
          }}
        }}

        @media(max-width:640px) {{
          .imagesHero,
          .imagesCard {{
            padding:22px;
          }}

          .imagesUploadForm {{
            grid-template-columns:1fr;
          }}

          .imagesUploadForm .btn,
          .imagesCardActions .btn,
          .imagesCardActions form,
          .imagesCardActions button,
          .imagesCardHead .btn {{
            width:100%;
          }}

          .imagesCardHead {{
            flex-direction:column;
            align-items:flex-start;
          }}
        }}
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Immagini",
        subtitle="Immagini lotto",
        body_html=body,
        actions_html=actions,
        user_email=user.get("email", ""),
        role=role,
        credits=balances,
    ))


@router.post("/app/wine/{wine_id}/images/upload")
def images_upload(request: Request, wine_id: int, kind: str = Form(...), image: UploadFile = File(...)):
    kind = (kind or "").strip().lower()

    if kind not in ("front", "back"):
        raise HTTPException(400, "kind non valido")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _wine(cur, int(wine_id))

    require_any_role(
        request,
        ("winery", "studio", "admin"),
        winery_id=int(w["winery_id"]),
        need="edit",
    )

    ctype = (image.content_type or "").lower().strip()

    if ctype and ctype not in ALLOWED_CONTENT_TYPES:
        return RedirectResponse(
            f"/app/wine/{wine_id}/images?msg=Formato%20non%20supportato",
            status_code=303,
        )

    data = _read_limited(image, MAX_UPLOAD_BYTES)

    if data is None:
        return RedirectResponse(
            f"/app/wine/{wine_id}/images?msg=File%20troppo%20grande%20(max%205MB)",
            status_code=303,
        )

    if not data:
        return RedirectResponse(
            f"/app/wine/{wine_id}/images?msg=File%20vuoto",
            status_code=303,
        )

    fmt = _validate_image_bytes(data)

    if not fmt:
        return RedirectResponse(
            f"/app/wine/{wine_id}/images?msg=Immagine%20non%20valida%20(o%20troppo%20grande)",
            status_code=303,
        )

    ext = _safe_ext(image.filename or "")

    if ext not in ALLOWED_EXT:
        ext = _ext_from_format(fmt)
    else:
        ext = _ext_from_format(fmt)

    try:
        paths = _save_images(int(wine_id), kind, data, ext)
    except Exception:
        return RedirectResponse(
            f"/app/wine/{wine_id}/images?msg=Errore%20salvataggio%20immagine",
            status_code=303,
        )

    if not all(
        os.path.isfile(os.path.join(UPLOADS_DIR, relative))
        and os.access(os.path.join(UPLOADS_DIR, relative), os.R_OK)
        for relative in paths.values()
    ):
        return RedirectResponse(
            f"/app/wine/{wine_id}/images?msg=File%20salvato%20ma%20non%20leggibile",
            status_code=303,
        )

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO wine_assets (wine_id, kind, img_original, img_optimized, img_thumb, updated_at)
                VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (wine_id, kind) DO UPDATE SET
                  img_original=EXCLUDED.img_original,
                  img_optimized=EXCLUDED.img_optimized,
                  img_thumb=EXCLUDED.img_thumb,
                  updated_at=EXCLUDED.updated_at
                """,
                (
                    int(wine_id),
                    kind,
                    paths["img_original"],
                    paths["img_optimized"],
                    paths["img_thumb"],
                    now(),
                ),
            )
            if cur.rowcount != 1:
                conn.rollback()
                return RedirectResponse(
                    f"/app/wine/{wine_id}/images?msg=Database%20immagine%20non%20aggiornato",
                    status_code=303,
                )
            conn.commit()

    return RedirectResponse(f"/app/wine/{wine_id}/images?msg=Caricato", status_code=303)


@router.post("/app/wine/{wine_id}/images/delete")
def images_delete(request: Request, wine_id: int, kind: str = Form(...)):
    kind = (kind or "").strip().lower()

    if kind not in ("front", "back"):
        raise HTTPException(400, "kind non valido")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _wine(cur, int(wine_id))

    require_any_role(
        request,
        ("winery", "studio", "admin"),
        winery_id=int(w["winery_id"]),
        need="edit",
    )

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "DELETE FROM wine_assets WHERE wine_id=%s AND kind=%s",
                (int(wine_id), kind),
            )
            conn.commit()

    try:
        folder = os.path.join(UPLOAD_BASE, str(wine_id), kind)

        for fn in ("optimized.jpg", "thumb.webp"):
            p = os.path.join(folder, fn)
            if os.path.exists(p):
                os.remove(p)

        if os.path.isdir(folder):
            for fn in os.listdir(folder):
                if fn.startswith("original."):
                    p = os.path.join(folder, fn)
                    try:
                        os.remove(p)
                    except Exception:
                        pass

    except Exception:
        pass

    return RedirectResponse(f"/app/wine/{wine_id}/images?msg=Eliminato", status_code=303)
