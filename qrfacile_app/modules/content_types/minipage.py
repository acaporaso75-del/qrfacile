"""Mini-pagina: logo, title, short text and up to six action buttons."""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path
from urllib.parse import quote_plus

from fastapi.responses import HTMLResponse, Response
from PIL import Image

from qrfacile_app.modules.content_types.base import ContentError, read_limited
from qrfacile_app.modules.content_types.link import valid_url
from qrfacile_app.services.storage import get_uploads_dir
from qrfacile_app.ui_shell import esc

MAX_TITLE = 80
MAX_TEXT = 600
MAX_BUTTONS = 6
MAX_LOGO_BYTES = 5 * 1024 * 1024
# A small file can still decode to a huge bitmap: refuse before decoding.
MAX_LOGO_PIXELS = 25_000_000
BUTTON_KINDS = {
    "call": "Chiama",
    "whatsapp": "WhatsApp",
    "email": "Email",
    "map": "Mappa",
    "site": "Sito",
    "instagram": "Instagram",
    "facebook": "Facebook",
}


def _button_href(kind: str, value: str) -> str:
    value = (value or "").strip()
    if kind == "call":
        digits = re.sub(r"[^\d+]", "", value)
        if not re.fullmatch(r"\+?\d{6,20}", digits):
            raise ContentError("Numero di telefono non valido.")
        return f"tel:{digits}"
    if kind == "whatsapp":
        digits = re.sub(r"\D", "", value)
        if not 8 <= len(digits) <= 15:
            raise ContentError("Numero WhatsApp non valido: indica prefisso internazionale e numero.")
        return f"https://wa.me/{digits}"
    if kind == "email":
        if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ContentError("Indirizzo email non valido.")
        return f"mailto:{value}"
    if kind == "map":
        if not 3 <= len(value) <= 200:
            raise ContentError("Indica l'indirizzo per la mappa.")
        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(value)}"
    if kind in ("site", "instagram", "facebook"):
        if not valid_url(value):
            raise ContentError(f"Indirizzo non valido per il pulsante {BUTTON_KINDS[kind]}: usa https://...")
        return value
    raise ContentError("Tipo di pulsante non disponibile.")


def _save_logo(upload, qr_item_id: int) -> str:
    data = read_limited(upload, MAX_LOGO_BYTES)
    if data is None:
        raise ContentError("Il logo supera i 5 MB.")
    try:
        image = Image.open(io.BytesIO(data))
        fmt = (image.format or "").upper()
        image.verify()
    except Exception as exc:
        raise ContentError("Il logo deve essere un'immagine JPG, PNG o WebP.") from exc
    if fmt not in ("JPEG", "PNG", "WEBP"):
        raise ContentError("Il logo deve essere un'immagine JPG, PNG o WebP.")
    width, height = Image.open(io.BytesIO(data)).size
    if width * height > MAX_LOGO_PIXELS:
        raise ContentError("Il logo è troppo grande: usa un'immagine sotto i 5000 × 5000 pixel.")
    image = Image.open(io.BytesIO(data))
    image.thumbnail((512, 512))
    image = image.convert("RGBA")
    digest = hashlib.sha256(data).hexdigest()[:16]
    relative = f"modules/link/{int(qr_item_id)}/logo-{digest}.png"
    target = Path(get_uploads_dir()) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=True)
    return relative


class MiniPageType:
    key = "minipage"
    label = "Mini-pagina"

    def parse(self, form, files, previous, *, qr_item_id):
        title = (form.get("minipage_title") or "").strip()
        text = (form.get("minipage_text") or "").strip()
        if not title:
            raise ContentError("Inserisci il titolo della mini-pagina.")
        if len(title) > MAX_TITLE:
            raise ContentError("Il titolo può avere al massimo 80 caratteri.")
        if len(text) > MAX_TEXT:
            raise ContentError("Il testo può avere al massimo 600 caratteri.")
        buttons = []
        for index in range(1, 21):
            kind = (form.get(f"minipage_button_kind_{index}") or "").strip()
            value = (form.get(f"minipage_button_value_{index}") or "").strip()
            if not kind and not value:
                continue
            if kind not in BUTTON_KINDS:
                raise ContentError("Tipo di pulsante non disponibile.")
            buttons.append({"kind": kind, "value": value, "href": _button_href(kind, value)})
        if len(buttons) > MAX_BUTTONS:
            raise ContentError("Puoi aggiungere al massimo 6 pulsanti.")
        content = {"title": title, "text": text, "buttons": buttons}
        upload = files.get("minipage_logo")
        if upload is not None and getattr(upload, "filename", ""):
            content["logo"] = _save_logo(upload, qr_item_id)
        elif previous and previous.get("logo"):
            content["logo"] = previous["logo"]
        return content

    def is_complete(self, content: dict) -> bool:
        return bool(content.get("title"))

    def files(self, content: dict) -> set[str]:
        return {content["logo"]} if content.get("logo") else set()

    def public_response(self, content: dict, *, slug: str) -> Response:
        logo = ""
        if content.get("logo"):
            logo = f'<img class="logo" src="/d/{esc(slug)}/logo" alt="Logo {esc(content["title"])}">'
        buttons = "".join(
            f'<a class="button" href="{esc(b["href"])}" rel="noopener">{esc(BUTTON_KINDS.get(b["kind"], b["kind"]))}</a>'
            for b in content.get("buttons") or []
        )
        text = f'<p class="text">{esc(content.get("text") or "")}</p>' if content.get("text") else ""
        html = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(content["title"])}</title>
<style>
body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f5f7fb;color:#0f172a}}
main{{max-width:520px;margin:0 auto;padding:28px 18px}}
.card{{background:#fff;border:1px solid #e3e8f0;border-radius:22px;padding:24px;text-align:center;box-shadow:0 14px 34px rgba(15,23,42,.08)}}
.logo{{width:96px;height:96px;object-fit:contain;border-radius:18px;margin-bottom:12px}}
h1{{font-size:26px;margin:6px 0 10px}}
.text{{color:#334155;line-height:1.55;white-space:pre-line}}
.buttons{{display:grid;gap:10px;margin-top:18px}}
.button{{display:block;padding:14px;border-radius:14px;background:#0f766e;color:#fff;font-weight:800;text-decoration:none}}
footer{{margin-top:18px;text-align:center;font-size:12px;color:#556377}}
footer a{{color:#556377}}
</style></head>
<body><main><div class="card">{logo}<h1>{esc(content["title"])}</h1>{text}<div class="buttons">{buttons}</div></div>
<footer>Pagina creata con QRFacile · <a href="/segnala/{esc(slug)}">Segnala contenuto</a></footer></main></body></html>"""
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    def editor_html(self, content: dict | None) -> str:
        content = content or {}
        rows = []
        buttons = list(content.get("buttons") or [])
        for index in range(1, MAX_BUTTONS + 1):
            current = buttons[index - 1] if index <= len(buttons) else {}
            options = '<option value="">Nessuno</option>' + "".join(
                f'<option value="{k}"{" selected" if current.get("kind") == k else ""}>{v}</option>'
                for k, v in BUTTON_KINDS.items()
            )
            rows.append(f"""
            <div class="minipageButtonRow" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:8px">
              <div><label for="mp-kind-{index}">Pulsante {index}</label>
                <select id="mp-kind-{index}" name="minipage_button_kind_{index}">{options}</select></div>
              <div><label for="mp-value-{index}">Numero, email, indirizzo o link</label>
                <input id="mp-value-{index}" class="input" name="minipage_button_value_{index}" value="{esc(current.get("value", ""))}"></div>
            </div>""")
        return f"""
        <label for="mp-title">Titolo (massimo 80 caratteri)</label>
        <input id="mp-title" class="input" name="minipage_title" maxlength="80" value="{esc(content.get("title", ""))}">
        <label for="mp-text">Testo breve (massimo 600 caratteri)</label>
        <textarea id="mp-text" class="input" name="minipage_text" maxlength="600" rows="4">{esc(content.get("text", ""))}</textarea>
        <label for="mp-logo">Logo (facoltativo, JPG/PNG/WebP fino a 5 MB)</label>
        <input id="mp-logo" class="input" type="file" name="minipage_logo" accept="image/png,image/jpeg,image/webp">
        {''.join(rows)}
        """
