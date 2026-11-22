"""Shared public page shell for content types (no script, everything escaped by callers)."""
from __future__ import annotations

from fastapi.responses import HTMLResponse

from qrfacile_app.ui_shell import esc

_CSS = """
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f5f7fb;color:#0f172a}
main{max-width:560px;margin:0 auto;padding:28px 18px}
.card{background:#fff;border:1px solid #e3e8f0;border-radius:22px;padding:24px;box-shadow:0 14px 34px rgba(15,23,42,.08)}
h1{font-size:26px;margin:4px 0 12px}
p{color:#334155;line-height:1.55}
.text{white-space:pre-line}
.big{font-size:24px;font-weight:800;word-break:break-all;background:#f1f5f9;border-radius:12px;padding:10px 12px;user-select:all}
.button{display:block;padding:14px;border-radius:14px;background:#0f766e;color:#fff;font-weight:800;text-decoration:none;text-align:center;margin-top:10px}
.grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(min(100%,150px),1fr));margin-top:12px}
.grid img{width:100%;height:auto;border-radius:12px;display:block}
footer{margin-top:18px;text-align:center;font-size:12px;color:#556377}
footer a{color:#556377}
"""


def public_page(title: str, inner_html: str, *, slug: str) -> HTMLResponse:
    html = (
        "<!doctype html><html lang=\"it\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{esc(title)}</title><style>{_CSS}</style></head><body><main>"
        f"<div class=\"card\">{inner_html}</div>"
        f"<footer>Pagina creata con QRFacile · <a href=\"/segnala/{esc(slug)}\">Segnala contenuto</a></footer>"
        "</main></body></html>"
    )
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


def field(name: str, label: str, value: str = "", *, hint: str = "", type_: str = "text", maxlength: int = 200,
          prefix: str = "") -> str:
    control_id = f"{prefix or name}-{name}".replace("_", "-")
    help_html = f'<p class="muted" style="font-size:14px;margin:2px 0 0">{esc(hint)}</p>' if hint else ""
    return (
        f'<div><label for="{control_id}">{esc(label)}</label>'
        f'<input id="{control_id}" class="input" type="{type_}" name="{name}" maxlength="{maxlength}" '
        f'value="{esc(value or "")}">{help_html}</div>'
    )


def text(form, key: str, limit: int) -> str:
    """Single-line value: control characters (CR/LF...) are never accepted."""
    value = " ".join(str(form.get(key) or "").split())
    return value[:limit]
