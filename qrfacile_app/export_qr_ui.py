import io
import os
import re
import zipfile
import smtplib
from email.utils import parseaddr
from email.message import EmailMessage
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Request, Query, HTTPException, Body
from fastapi.responses import HTMLResponse, Response, JSONResponse
from pydantic import BaseModel, ConfigDict
from psycopg.rows import dict_row

import qrcode
from qrcode.constants import ERROR_CORRECT_Q
from PIL import Image

from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm as rl_mm
from reportlab.lib.utils import ImageReader

try:
    import segno
except Exception:
    segno = None

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, esc
from qrfacile_app.audit import audit_log

router = APIRouter()


class PackageSendRequest(BaseModel):
    """Public contract for sending a print package."""

    model_config = ConfigDict(extra="forbid")
    to_email: str | None = None


_send_guard = Lock()
_recent_sends: dict[tuple[int, int, str], float] = {}
_DUPLICATE_WINDOW_SECONDS = 30.0


def _valid_email(value: str) -> bool:
    email = (value or "").strip().lower()
    parsed = parseaddr(email)[1]
    return bool(parsed == email and re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email))


def _send_error(message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"ok": False, "message": message}, status_code=status_code)

# -------------------------
# Preset stampa
# -------------------------
PRESETS = {
    "label_std": {"label": "Retro etichetta Standard · 20mm · 300dpi · PNG", "fmt": "png", "size_mm": 20, "dpi": 300},
    "label_pro": {"label": "Retro etichetta Premium · 25mm · 600dpi · PNG",  "fmt": "png", "size_mm": 25, "dpi": 600},
    "carton":    {"label": "Cartone / Scatola · 30mm · 300dpi · PNG",        "fmt": "png", "size_mm": 30, "dpi": 300},
    "fair":      {"label": "Fiera / Stand · 40mm · 300dpi · PNG",            "fmt": "png", "size_mm": 40, "dpi": 300},
    "a4_pdf":    {"label": "PDF A4 pronto stampa · QR centrato",             "fmt": "pdf_a4", "size_mm": 25, "dpi": 600},
}

ZIP_BUNDLE = [
    ("png_20_300", "png", 20, 300),
    ("png_25_600", "png", 25, 600),
    ("svg",        "svg", 25, 600),
    ("pdf_sq_25",  "pdf", 25, 600),
    ("pdf_a4",     "pdf_a4", 25, 600),
]


# -------------------------
# ACL helpers
# -------------------------

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

def _admin_active_winery_id(cur, user_id: int) -> int | None:
    cur.execute("SELECT admin_active_winery_id FROM users WHERE id=%s LIMIT 1", (int(user_id),))
    r = cur.fetchone() or {}
    wid = r.get("admin_active_winery_id")
    return int(wid) if wid else None


def _studio_can_export_wine(cur, studio_user_id: int, wine_id: int) -> bool:
    """
    Studio può esportare SOLO se è assegnato ad almeno una label di quel lotto
    con can_export=TRUE.
    """
    cur.execute(
        """
        SELECT 1
        FROM wine_labels wl
        JOIN label_collaborators lc ON lc.wine_label_id = wl.id
        WHERE wl.wine_id=%s
          AND lc.collaborator_user_id=%s
          AND lc.active=TRUE
          AND lc.can_export=TRUE
        LIMIT 1
        """,
        (int(wine_id), int(studio_user_id)),
    )
    return bool(cur.fetchone())


def _require_export_access(request: Request, wine_id: int) -> dict:
    """
    Regole:
    - winery: owner della cantina del lotto
    - studio: studio_clients.can_view sulla cantina + label_collaborators.can_export su almeno una label del lotto
    - admin: SOLO con contesto cantina attivo (users.admin_active_winery_id) e match winery_id del lotto
    """
    u = require_any_role(request, ("winery", "studio", "admin"))
    role = (u.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT qw.id AS wine_id, qw.winery_id, w.owner_user_id
                FROM qr_wines qw
                JOIN wineries w ON w.id = qw.winery_id
                WHERE qw.id=%s
                LIMIT 1
                """,
                (int(wine_id),),
            )
            r = cur.fetchone()
            if not r:
                raise HTTPException(404, "Lotto non trovato")

            winery_id = int(r["winery_id"])
            owner_user_id = int(r["owner_user_id"])

            # ADMIN: serve contesto cantina attivo
            if role == "admin":
                active_wid = _admin_active_winery_id(cur, int(u["id"]))
                if not active_wid:
                    raise HTTPException(403, "Admin senza contesto cantina attivo")
                if int(active_wid) != winery_id:
                    raise HTTPException(403, "Contesto cantina non corrisponde al lotto")
                return u

            # WINERY owner
            if role == "winery" and int(u["id"]) == owner_user_id:
                return u

            # STUDIO
            if role == "studio":
                cur.execute(
                    """
                    SELECT can_view
                    FROM studio_clients
                    WHERE studio_user_id=%s AND winery_id=%s
                    LIMIT 1
                    """,
                    (int(u["id"]), winery_id),
                )
                row = cur.fetchone()
                if not row or not bool(row.get("can_view")):
                    raise HTTPException(403, "Forbidden")

                if not _studio_can_export_wine(cur, int(u["id"]), int(wine_id)):
                    raise HTTPException(403, "Forbidden")

                return u

    raise HTTPException(403, "Forbidden")


# -------------------------
# Utility
# -------------------------
def _safe_filename(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9_\-]+", "", s)
    return s[:90] or "qrfacile"


def _wine(cur, wine_id: int):
    cur.execute("""
      SELECT qw.id AS wine_id, qw.winery_id, qw.wine_name, qw.vintage, qw.lot,
             qi.slug, w.name AS winery_name
      FROM qr_wines qw
      JOIN qr_items qi ON qi.id=qw.qr_item_id
      JOIN wineries w ON w.id=qw.winery_id
      WHERE qw.id=%s
      LIMIT 1
    """, (int(wine_id),))
    r = cur.fetchone()
    if not r:
        raise HTTPException(404, "Lotto non trovato")
    return r


def _public_url(request: Request, slug: str) -> str:
    base = getattr(request.app.state, "app_base_url", "").rstrip("/")
    if not base:
        base = f"{request.url.scheme}://{request.headers.get('host','localhost:8000')}"
    return f"{base}/e/{slug}"


def _mm_to_px(size_mm: int, dpi: int) -> int:
    inches = size_mm / 25.4
    px = int(inches * dpi)
    return max(260, px)


def _qr_img(url: str, size_mm: int, dpi: int) -> Image.Image:
    px = _mm_to_px(size_mm, dpi)
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_Q,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((px, px), Image.NEAREST)
    return img


def _qr_png(url: str, size_mm: int, dpi: int) -> bytes:
    img = _qr_img(url, size_mm, dpi)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _qr_jpg(url: str, size_mm: int, dpi: int) -> bytes:
    img = _qr_img(url, size_mm, dpi)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95, optimize=True)
    return buf.getvalue()


def _qr_svg(url: str) -> bytes:
    if segno is None:
        raise HTTPException(500, "SVG non disponibile (segno non installato)")
    qr = segno.make(url, error="q")
    buf = io.BytesIO()
    qr.save(buf, kind="svg", xmldecl=True, svgclass="qrfacile-qr")
    return buf.getvalue()


def _qr_pdf_square(url: str, size_mm: int, dpi: int) -> bytes:
    png = _qr_png(url, size_mm=size_mm, dpi=dpi)
    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=(size_mm*rl_mm, size_mm*rl_mm))
    img = ImageReader(io.BytesIO(png))
    c.drawImage(img, 0, 0, width=size_mm*rl_mm, height=size_mm*rl_mm, preserveAspectRatio=True, mask="auto")
    c.showPage()
    c.save()
    return buf.getvalue()


def _qr_pdf_a4(url: str, size_mm: int, dpi: int) -> bytes:
    png = _qr_png(url, size_mm=size_mm, dpi=dpi)
    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4

    qr_w = size_mm * rl_mm
    qr_h = size_mm * rl_mm
    x = (page_w - qr_w) / 2
    y = (page_h - qr_h) / 2

    img = ImageReader(io.BytesIO(png))
    c.drawImage(img, x, y, width=qr_w, height=qr_h, preserveAspectRatio=True, mask="auto")

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.35, 0.38, 0.41)
    c.drawCentredString(page_w/2, y - 10, "QRFACILE · QR pronto per stampa")
    c.showPage()
    c.save()
    return buf.getvalue()


def _build_zip_bundle(url: str, base_name: str) -> bytes:
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        for tag, fmt, size_mm, dpi in ZIP_BUNDLE:
            if fmt == "png":
                z.writestr(f"{base_name}_{tag}.png", _qr_png(url, size_mm, dpi))
            elif fmt == "jpg":
                z.writestr(f"{base_name}_{tag}.jpg", _qr_jpg(url, size_mm, dpi))
            elif fmt == "svg":
                z.writestr(f"{base_name}_{tag}.svg", _qr_svg(url))
            elif fmt == "pdf":
                z.writestr(f"{base_name}_{tag}.pdf", _qr_pdf_square(url, size_mm, dpi))
            elif fmt == "pdf_a4":
                z.writestr(f"{base_name}_{tag}_A4.pdf", _qr_pdf_a4(url, size_mm, dpi))
    return mem.getvalue()


def _smtp_send_zip(to_email: str, subject: str, body: str, zip_bytes: bytes, zip_name: str):
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "465").strip() or "465")
    user = os.getenv("SMTP_USER", "").strip()
    pw = os.getenv("SMTP_PASS", "").strip()
    from_email = (os.getenv("FROM_EMAIL", "") or user).strip()

    if not host or not from_email:
        raise HTTPException(500, "SMTP non configurato (SMTP_HOST/FROM_EMAIL)")
    if not user or not pw:
        raise HTTPException(500, "SMTP non configurato (SMTP_USER/SMTP_PASS)")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(zip_bytes, maintype="application", subtype="zip", filename=zip_name)

    with smtplib.SMTP_SSL(host, port) as s:
        s.login(user, pw)
        s.send_message(msg)


# -------------------------
# Routes
# -------------------------
@router.get("/app/wine/{wine_id}/export", response_class=HTMLResponse)
def export_page(request: Request, wine_id: int, preset: str = "label_pro", name: str = "", msg: str = "", err: str = ""):
    # ACL
    u = _require_export_access(request, wine_id)

    role = (u.get("role") or "").lower().strip()
    uid = int(u["id"])
    balances = {"wine": 0, "generic": 0}

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            balances = _balances(cur, uid)

    # admin senza contesto -> porta su /admin
    if (u.get("role") or "").lower().strip() == "admin" and "contesto" in (err or "").lower():
        return RedirectResponse("/admin", status_code=303)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _wine(cur, wine_id)

    slug = w["slug"]
    url = _public_url(request, slug)

    base_name = "_".join([
        _safe_filename(w["winery_name"]),
        _safe_filename(w["wine_name"]),
        _safe_filename(w.get("vintage") or ""),
        _safe_filename(w.get("lot") or ""),
        _safe_filename(slug),
    ]).strip("_")
    if name.strip():
        base_name = _safe_filename(name)

    if preset not in PRESETS:
        preset = "label_pro"

    actions = top_actions(
        (f"/app/wine/{int(wine_id)}?tab=export", "Torna al lotto"),
        ("/app/dashboard", "Dashboard"),
        ("/logout", "Logout"),
    )

    preset_options = "".join([
        f"<option value='{k}' {'selected' if k==preset else ''}>{esc(v['label'])}</option>"
        for k, v in PRESETS.items()
    ])

    body = f"""
    <section class="exportWrap">
      <div class="exportHero">
        <div>
          <div class="exportEyebrow">Export tipografico</div>
          <div class="h1">QR pronto per stampa</div>
          <div class="p">
            Genera file professionali per retro-etichetta, cartone, fiera o tipografia.
            PNG alta risoluzione, SVG vettoriale, PDF e ZIP completo.
          </div>

          <div class="exportMeta">
            <span><b>Vino</b> {esc(w["wine_name"] or "-")}</span>
            <span><b>Cantina</b> {esc(w["winery_name"] or "-")}</span>
            <span><b>Lotto</b> {esc(w.get("lot") or "-")}</span>
          </div>

          <div class="exportUrlBox">
            <div>URL contenuto nel QR</div>
            <code>{esc(url)}</code>
          </div>

          <div class="exportHint" style="margin-top:12px">
            Il QR generato è già quello definitivo e può essere inviato immediatamente al tipografo. La pagina pubblica non sarà visibile finché non saranno completati tutti i dati obbligatori e la pubblicazione non sarà confermata.
          </div>
        </div>

        <div class="exportHeroPreview">
          <div class="exportHeroPreviewHead">
            <div>
              <div class="exportSmallLabel">Preview</div>
              <b>{esc(PRESETS[preset]["label"])}</b>
            </div>
          </div>

          <div class="exportQrFrame">
            <img src="/app/wine/{int(wine_id)}/export/preview.png?preset={esc(preset)}"
                 alt="Preview QR">
          </div>
        </div>
      </div>

      <div class="exportFlow">
        <div class="exportStep done">
          <span>1</span>
          <div>
            <b>Compliance</b>
            <small>Dati completati o verificati</small>
          </div>
        </div>

        <div class="exportStep active">
          <span>2</span>
          <div>
            <b>Export</b>
            <small>Scegli formato e preset</small>
          </div>
        </div>

        <div class="exportStep">
          <span>3</span>
          <div>
            <b>Tipografia</b>
            <small>Invia ZIP o scarica file</small>
          </div>
        </div>
      </div>

      <div class="exportGrid">
        <div class="card exportPanel">
          <div class="exportPanelHead">
            <div>
              <div class="exportSmallLabel">Preset</div>
              <div class="h2">Formato di stampa</div>
            </div>
            <span class="exportIcon">🖨️</span>
          </div>

          <form method="get" action="/app/wine/{int(wine_id)}/export" class="exportForm">
            <div>
              <label>Preset tipografico</label>
              <select name="preset" required>{preset_options}</select>
            </div>

            <div>
              <label>Nome file</label>
              <input class="input" name="name" value="{esc(base_name)}">
            </div>

            <button class="btn btn-primary" type="submit">Aggiorna preview</button>
          </form>

          <div class="exportHint">
            Scegli il preset in base all’uso: retro etichetta, cartone, fiera o PDF A4.
          </div>
        </div>

        <div class="card exportPanel">
          <div class="exportPanelHead">
            <div>
              <div class="exportSmallLabel">Download</div>
              <div class="h2">File pronti</div>
            </div>
            <span class="exportIcon">⬇️</span>
          </div>

          <div class="exportDownloadGrid">
            <a class="exportDownloadCard" href="/app/wine/{int(wine_id)}/export/file?preset={esc(preset)}&name={esc(base_name)}">
              <b>Scarica preset</b>
              <span>File singolo nel formato scelto</span>
            </a>

            <a class="exportDownloadCard primary" href="/app/wine/{int(wine_id)}/export/zip?name={esc(base_name)}">
              <b>ZIP completo</b>
              <span>PNG, SVG, PDF e A4 in un pacchetto</span>
            </a>
          </div>

          <div class="exportHint">
            Lo ZIP completo è il formato consigliato per studi grafici e tipografie.
          </div>
        </div>
      </div>

      <div class="card exportPanel" style="margin-top:18px">
        <div class="exportPanelHead">
          <div>
            <div class="exportSmallLabel">Invio tipografia</div>
            <div class="h2">Invia pacchetto ZIP via email</div>
          </div>
          <span class="exportIcon">✉️</span>
        </div>

        <form action="/app/wine/{int(wine_id)}/export/send?name={esc(base_name)}" class="exportSendForm" data-package-send-form>
          <div>
            <label>Email destinatario</label>
            <input class="input" name="to_email" type="email" required autocomplete="email" placeholder="tipografia@example.com">
          </div>

          <button class="btn btn-primary" type="submit" data-package-send-button>Invia pacchetti</button>
        </form>
        <div class="exportHint" data-package-send-message role="status" aria-live="polite"></div>

        <div class="exportHint">
          Funzione riservata a cantina/admin. Gli studi possono esportare, ma non inviare email direttamente.
        </div>
      </div>

      <style>
        .exportWrap {{
          max-width:1180px;
          margin:0 auto;
        }}

        .exportHero {{
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
          grid-template-columns:minmax(0,1.25fr) 340px;
          gap:24px;
          align-items:center;
        }}

        .exportEyebrow {{
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

        .exportMeta {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:16px;
        }}

        .exportMeta span {{
          display:inline-flex;
          padding:8px 11px;
          border-radius:999px;
          background:rgba(255,255,255,.72);
          border:1px solid rgba(2,8,23,.07);
          color:#475569;
          font-size:12px;
          font-weight:850;
        }}

        .exportMeta b {{
          color:#0f172a;
          margin-right:4px;
        }}

        .exportUrlBox {{
          margin-top:18px;
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.72);
          border-radius:20px;
          padding:14px;
        }}

        .exportUrlBox div {{
          color:#64748b;
          font-size:11px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.07em;
          margin-bottom:6px;
        }}

        .exportUrlBox code {{
          display:block;
          font-size:12px;
          word-break:break-all;
          color:#0f766e;
          font-weight:850;
        }}

        .exportHeroPreview {{
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.76);
          border-radius:24px;
          padding:18px;
          box-shadow:0 18px 45px rgba(2,8,23,.06);
        }}

        .exportHeroPreviewHead {{
          margin-bottom:14px;
        }}

        .exportHeroPreviewHead b {{
          display:block;
          margin-top:4px;
          font-size:13px;
          line-height:1.35;
        }}

        .exportSmallLabel {{
          color:#64748b;
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.08em;
        }}

        .exportQrFrame {{
          display:flex;
          justify-content:center;
          align-items:center;
          border:1px solid rgba(2,8,23,.08);
          background:#fff;
          border-radius:22px;
          padding:22px;
        }}

        .exportQrFrame img {{
          width:230px;
          height:230px;
          display:block;
        }}

        .exportFlow {{
          display:grid;
          grid-template-columns:repeat(3,minmax(0,1fr));
          gap:14px;
          margin-top:18px;
        }}

        .exportStep {{
          display:flex;
          gap:12px;
          align-items:flex-start;
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          padding:16px;
          background:rgba(255,255,255,.78);
          box-shadow:0 12px 30px rgba(2,8,23,.04);
        }}

        .exportStep.active {{
          background:linear-gradient(135deg,rgba(191,245,230,.78),rgba(207,232,255,.62));
          border-color:rgba(20,184,166,.18);
        }}

        .exportStep.done span {{
          background:#10b981;
          color:#fff;
        }}

        .exportStep span {{
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

        .exportStep b {{
          display:block;
          font-size:15px;
          font-weight:950;
        }}

        .exportStep small {{
          display:block;
          margin-top:3px;
          color:#64748b;
          font-size:12px;
          font-weight:750;
          line-height:1.35;
        }}

        .exportGrid {{
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:18px;
          margin-top:18px;
        }}

        .exportPanel {{
          padding:22px;
        }}

        .exportPanelHead {{
          display:flex;
          justify-content:space-between;
          gap:14px;
          align-items:flex-start;
          margin-bottom:16px;
        }}

        .exportIcon {{
          width:40px;
          height:40px;
          border-radius:16px;
          display:inline-flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.88),rgba(207,232,255,.80));
          border:1px solid rgba(2,8,23,.07);
          font-size:19px;
          flex:0 0 auto;
        }}

        .exportForm {{
          display:grid;
          gap:14px;
        }}

        .exportDownloadGrid {{
          display:grid;
          gap:12px;
        }}

        .exportDownloadCard {{
          display:block;
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.72);
          border-radius:20px;
          padding:16px;
        }}

        .exportDownloadCard.primary {{
          background:rgba(236,253,245,.86);
          border-color:rgba(20,184,166,.18);
        }}

        .exportDownloadCard b {{
          display:block;
          font-size:16px;
          font-weight:950;
        }}

        .exportDownloadCard span {{
          display:block;
          margin-top:5px;
          color:#64748b;
          font-size:13px;
          font-weight:750;
          line-height:1.4;
        }}

        .exportHint {{
          margin-top:14px;
          color:#64748b;
          font-size:13px;
          font-weight:750;
          line-height:1.45;
        }}

        .exportSendForm {{
          display:grid;
          grid-template-columns:minmax(0,1fr) auto;
          gap:12px;
          align-items:end;
        }}

        @media(max-width:980px) {{
          .exportHero,
          .exportGrid,
          .exportFlow {{
            grid-template-columns:1fr;
          }}
        }}

        @media(max-width:560px) {{
          .exportHero,
          .exportPanel {{
            padding:22px;
          }}

          .exportSendForm {{
            grid-template-columns:1fr;
          }}

          .exportSendForm .btn,
          .exportForm .btn {{
            width:100%;
          }}
        }}
      </style>
      <script>
      (() => {{
        const form = document.querySelector('[data-package-send-form]');
        if (!form) return;
        const email = form.elements.to_email;
        const button = form.querySelector('[data-package-send-button]');
        const message = document.querySelector('[data-package-send-message]');
        let sending = false;
        const show = (text, error = false) => {{
          message.textContent = text;
          message.style.color = error ? '#b42318' : '#067647';
        }};
        form.addEventListener('submit', async (event) => {{
          event.preventDefault();
          if (sending) return;
          const toEmail = email.value.trim();
          if (!toEmail) {{ show('Inserisci l’indirizzo email del destinatario', true); email.focus(); return; }}
          if (!email.checkValidity()) {{ show('Inserisci un indirizzo email valido', true); email.focus(); return; }}
          sending = true;
          button.disabled = true;
          button.setAttribute('aria-busy', 'true');
          show('Invio in corso…');
          try {{
            const response = await fetch(form.action, {{
              method: 'POST',
              headers: {{'Content-Type': 'application/json', 'Accept': 'application/json'}},
              credentials: 'same-origin',
              body: JSON.stringify({{to_email: toEmail}})
            }});
            let data = {{}};
            try {{ data = await response.json(); }} catch (_) {{ /* never expose raw server bodies */ }}
            if (!response.ok || !data.ok) throw new Error(data.message || 'Invio non riuscito. Riprova.');
            show('Pacchetti inviati correttamente');
            form.reset();
          }} catch (error) {{
            const safe = error.message === 'Destinatario non trovato' ? error.message :
              (error.message === 'Invio già effettuato. Attendi prima di riprovare.' ? error.message : 'Invio non riuscito. Riprova.');
            show(safe, true);
          }} finally {{
            sending = false;
            button.disabled = false;
            button.removeAttribute('aria-busy');
          }}
        }});
      }})();
      </script>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Export",
        subtitle="Export lotto",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=u.get("email", ""),
        role=role,
        credits=balances,
    ))


@router.get("/app/wine/{wine_id}/export/preview.png")
def export_preview_png(request: Request, wine_id: int, preset: str = Query("label_pro")):
    u = _require_export_access(request, wine_id)
    if preset not in PRESETS:
        preset = "label_pro"
    cfg = PRESETS[preset]

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _wine(cur, wine_id)

    url = _public_url(request, w["slug"])
    return Response(content=_qr_png(url, size_mm=int(cfg["size_mm"]), dpi=300), media_type="image/png")


@router.get("/app/wine/{wine_id}/export/file")
def export_file(request: Request, wine_id: int, preset: str = Query("label_pro"), name: str = Query("qrfacile")):
    u = _require_export_access(request, wine_id)
    if preset not in PRESETS:
        raise HTTPException(400, "Preset non valido")

    cfg = PRESETS[preset]
    fmt = cfg["fmt"]
    size_mm = int(cfg["size_mm"])
    dpi = int(cfg["dpi"])
    name = _safe_filename(name)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _wine(cur, wine_id)

    url = _public_url(request, w["slug"])

    audit_log(u, "export_file", "wine", int(wine_id),
              request.client.host if request.client else "",
              request.headers.get("user-agent", ""),
              {"preset": preset, "fmt": fmt, "name": name})

    if fmt == "png":
        data = _qr_png(url, size_mm=size_mm, dpi=dpi)
        return Response(content=data, media_type="image/png",
                        headers={"Content-Disposition": f'attachment; filename="{name}_{size_mm}mm_{dpi}dpi.png"'})

    if fmt == "jpg":
        data = _qr_jpg(url, size_mm=size_mm, dpi=dpi)
        return Response(content=data, media_type="image/jpeg",
                        headers={"Content-Disposition": f'attachment; filename="{name}_{size_mm}mm_{dpi}dpi.jpg"'})

    if fmt == "svg":
        data = _qr_svg(url)
        return Response(content=data, media_type="image/svg+xml",
                        headers={"Content-Disposition": f'attachment; filename="{name}.svg"'})

    if fmt == "pdf":
        data = _qr_pdf_square(url, size_mm=size_mm, dpi=dpi)
        return Response(content=data, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}_{size_mm}mm.pdf"'})

    if fmt == "pdf_a4":
        data = _qr_pdf_a4(url, size_mm=size_mm, dpi=dpi)
        return Response(content=data, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}_A4.pdf"'})

    raise HTTPException(400, "Formato non supportato")


@router.get("/app/wine/{wine_id}/export/zip")
def export_zip(request: Request, wine_id: int, name: str = Query("qrfacile")):
    u = _require_export_access(request, wine_id)
    name = _safe_filename(name)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _wine(cur, wine_id)

    url = _public_url(request, w["slug"])
    zip_bytes = _build_zip_bundle(url, name)

    audit_log(u, "export_zip", "wine", int(wine_id),
              request.client.host if request.client else "",
              request.headers.get("user-agent", ""),
              {"name": name})

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}_bundle.zip"'}
    )


@router.post("/app/wine/{wine_id}/export/send")
def export_send(
    request: Request,
    wine_id: int,
    payload: PackageSendRequest | None = Body(default=None),
    name: str = Query("qrfacile"),
):
    u = _require_export_access(request, wine_id)

    # studio può esportare, ma invio email è “sensibile”: lo teniamo consentito SOLO a winery/admin
    role = (u.get("role") or "").lower().strip()
    if role == "studio":
        return _send_error("Non sei autorizzato a inviare questi pacchetti", 403)

    to_email = ((payload.to_email if payload else "") or "").strip().lower()
    if not to_email:
        return _send_error("Inserisci l’indirizzo email del destinatario", 400)
    if not _valid_email(to_email):
        return _send_error("Inserisci un indirizzo email valido", 422)

    name = _safe_filename(name)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _wine(cur, wine_id)

    # The ACL above resolves the wine's winery server-side. Never trust a winery id
    # from the browser. A short idempotency window also stops double clicks/retries.
    duplicate_key = (int(u["id"]), int(wine_id), to_email)
    now_mono = monotonic()
    with _send_guard:
        expired = [key for key, sent_at in _recent_sends.items() if now_mono - sent_at >= _DUPLICATE_WINDOW_SECONDS]
        for key in expired:
            _recent_sends.pop(key, None)
        if duplicate_key in _recent_sends:
            return _send_error("Invio già effettuato. Attendi prima di riprovare.", 409)
        _recent_sends[duplicate_key] = now_mono

    url = _public_url(request, w["slug"])
    zip_bytes = _build_zip_bundle(url, name)
    zip_name = f"{name}_bundle.zip"

    subject = f"QRFACILE · QR stampa · {w['winery_name']} · {w['wine_name']}"
    body = f"""Ciao,
in allegato trovi i file QR pronti per la stampa.

Lotto: {w.get('lot') or '-'}
Slug: {w.get('slug')}

Grazie.
"""

    try:
        _smtp_send_zip(to_email, subject, body, zip_bytes, zip_name)
    except smtplib.SMTPRecipientsRefused:
        with _send_guard:
            _recent_sends.pop(duplicate_key, None)
        return _send_error("Destinatario non trovato", 404)
    except Exception:
        with _send_guard:
            _recent_sends.pop(duplicate_key, None)
        return _send_error("Invio non riuscito. Riprova.", 503)

    audit_log(u, "export_send_email", "wine", int(wine_id),
              request.client.host if request.client else "",
              request.headers.get("user-agent", ""),
              {"to": to_email, "name": name})

    return {"ok": True, "message": "Pacchetti inviati correttamente"}
