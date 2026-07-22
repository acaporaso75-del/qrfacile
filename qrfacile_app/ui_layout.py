import html
from typing import Optional

def esc(s: str) -> str:
    return html.escape(s or "")

def pill(text: str, kind: str = "default") -> str:
    cls = "pill"
    if kind == "green":
        cls += " pill-green"
    elif kind == "muted":
        cls += " pill-muted"
    elif kind == "warn":
        cls += " pill-warn"
    return f"<span class='{cls}'>{esc(text)}</span>"

def banner(msg: str = "", err: str = "") -> str:
    out = []
    if msg:
        out.append(f"<div class='note'><b>OK:</b> {esc(msg)}</div>")
    if err:
        out.append(f"<div class='note note-err'><b>Errore:</b> {esc(err)}</div>")
    return "\n".join(out)

def topbar(title: str, subtitle: str, actions_html: str = "") -> str:
    return f"""
    <div class="topbar">
      <div class="brand">
        <div class="brand-dot"></div>
        <div>
          <div class="brand-title">{esc(title)}</div>
          <div class="brand-sub">{esc(subtitle)}</div>
        </div>
      </div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center">
        {actions_html}
      </div>
    </div>
    """

def layout(page_title: str, subtitle: str, body_html: str, actions_html: str = "", msg: str = "", err: str = "") -> str:
    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(page_title)}</title>
<link rel="stylesheet" href="/static/app.css">
<style>
.pill{{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;border:1px solid rgba(2,8,23,.14);background:rgba(255,255,255,.75);font-weight:850;font-size:12px}}
.pill-green{{border-color:rgba(34,197,94,.35);background:rgba(34,197,94,.10)}}
.pill-warn{{border-color:rgba(245,158,11,.35);background:rgba(245,158,11,.10)}}
.pill-muted{{opacity:.78}}
.note-err{{border-color:rgba(176,0,32,.28);background:rgba(176,0,32,.06);color:#7a0016}}
</style>
</head>
<body>
<div class="container">
  {topbar("QRFACILE", subtitle, actions_html)}
  {banner(msg, err)}
  {body_html}
</div>
</body>
</html>"""

def error_page(code: int, title: str, detail: str, back_href: str = "/app/dashboard") -> str:
    return layout(
        page_title=f"QRFACILE · {code}",
        subtitle=title,
        actions_html=f"<a class='pill' href='{esc(back_href)}'>Torna</a>",
        body_html=f"""
        <div class="card" style="max-width:860px;margin-top:14px">
          <div class="h2">{esc(title)}</div>
          <div class="p" style="margin-top:10px">{esc(detail)}</div>
          <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap">
            <a class="btn btn-primary" href="{esc(back_href)}">Torna</a>
            <a class="btn" href="/logout">Logout</a>
          </div>
        </div>
        """
    )

