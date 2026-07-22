import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.ui_shell import esc

router = APIRouter()


def _clean_legacy_content(html: str) -> str:
    html = html or ""

    # Rimozione difensiva: gli script WP non servono e possono creare problemi.
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.I | re.S)

    # Rimozione commenti blocchi Gutenberg.
    html = re.sub(r"<!--\s*/?wp:[^>]*-->", "", html, flags=re.I)

    return html.strip()


@router.get("/{legacy_slug}", response_class=HTMLResponse)
@router.get("/{legacy_slug}/", response_class=HTMLResponse)
def legacy_page(legacy_slug: str):
    slug = (legacy_slug or "").strip().strip("/")

    # PostgreSQL non accetta byte NUL nei campi testuali.
    # Blocchiamo input anomali prima di passarli alla query.
    if "\x00" in slug:
        raise HTTPException(400, "Invalid slug")

    # Limite difensivo per evitare input eccessivamente lunghi.
    if len(slug) > 255:
        raise HTTPException(404, "Not found")

    # Evita collisioni con le rotte reali dell'app.
    blocked = {
        "app",
        "admin",
        "login",
        "logout",
        "pricing",
        "static",
        "uploads",
        "paypal",
        "legal",
        "privacy",
        "cookies",
        "terms",
        "register-winery",
        "register-studio",
        "register-interest",
        "demo",
        "e",
        "favicon.ico",
    }

    if not slug or slug in blocked:
        raise HTTPException(404, "Not found")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT slug, title, content_html, source_url
                FROM legacy_pages
                WHERE slug=%s
                  AND active=TRUE
                LIMIT 1
            """, (slug,))
            row = cur.fetchone()

    if not row:
        raise HTTPException(404, "Legacy page not found")

    title = row.get("title") or slug
    content = _clean_legacy_content(row.get("content_html") or "")

    if not content:
        content = "<p>Contenuto legacy importato non disponibile.</p>"

    html = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · QRFACILE</title>
<meta name="robots" content="noindex,follow">
<style>
* {{ box-sizing:border-box; }}

body {{
  margin:0;
  font-family:Arial, sans-serif;
  background:
    radial-gradient(circle at 0% 0%, rgba(20,184,166,.10), transparent 30%),
    radial-gradient(circle at 100% 0%, rgba(14,165,233,.08), transparent 30%),
    #f8fafc;
  color:#0f172a;
}}

.wrap {{
  max-width:980px;
  margin:0 auto;
  padding:18px;
}}

.top {{
  border:1px solid #e5e7eb;
  border-radius:24px;
  background:#ffffff;
  padding:18px;
  box-shadow:0 18px 45px rgba(2,8,23,.06);
  margin-bottom:16px;
}}

.brand {{
  display:flex;
  align-items:center;
  gap:12px;
}}

.brand img {{
  width:44px;
  height:44px;
  border-radius:14px;
  background:#fff;
  border:1px solid #e5e7eb;
  padding:6px;
}}

.brand b {{
  display:block;
  font-size:18px;
  font-weight:950;
}}

.brand span {{
  display:block;
  margin-top:3px;
  color:#64748b;
  font-size:13px;
  font-weight:700;
}}

.notice {{
  margin-bottom:16px;
  border:1px solid rgba(20,184,166,.16);
  background:#ecfdf5;
  color:#0f766e;
  border-radius:18px;
  padding:13px;
  font-size:13px;
  font-weight:800;
}}

.card {{
  border:1px solid #e5e7eb;
  border-radius:24px;
  background:#ffffff;
  padding:22px;
  box-shadow:0 18px 45px rgba(2,8,23,.06);
}}

h1 {{
  margin:0 0 16px;
  font-size:clamp(28px,5vw,46px);
  line-height:1;
  letter-spacing:-1.2px;
}}

.legacy {{
  color:#334155;
  font-size:15px;
  line-height:1.65;
}}

.legacy img {{
  max-width:100%;
  height:auto;
}}

.legacy table {{
  max-width:100%;
  width:100%;
  border-collapse:collapse;
}}

.legacy td,
.legacy th {{
  border:1px solid #e5e7eb;
  padding:8px;
}}

@media(max-width:640px) {{
  .wrap {{
    padding:12px;
  }}

  .top,
  .card {{
    border-radius:20px;
    padding:16px;
  }}
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div class="brand">
      <img src="/static/qrfacile.svg" alt="QRFACILE">
      <div>
        <b>QRFACILE</b>
        <span>Pagina legacy mantenuta per compatibilità QR già attivi</span>
      </div>
    </div>
  </div>

  <div class="notice">
    Questa pagina è stata mantenuta per non interrompere QR già stampati o distribuiti.
  </div>

  <main class="card">
    <h1>{esc(title)}</h1>
    <div class="legacy">
      {content}
    </div>
  </main>
</div>
</body>
</html>"""

    return HTMLResponse(html)
