"""Link: the QR redirects to any http(s) address."""
from __future__ import annotations

from urllib.parse import urlsplit

from fastapi.responses import RedirectResponse, Response

from qrfacile_app.modules.content_types.base import ContentError
from qrfacile_app.ui_shell import esc

MAX_URL_LENGTH = 2000


def valid_url(url: str) -> bool:
    url = (url or "").strip()
    if not url or len(url) > MAX_URL_LENGTH:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


class LinkType:
    key = "link"
    label = "Link"

    def parse(self, form, files, previous, *, qr_item_id):
        url = (form.get("link_url") or "").strip()
        if not valid_url(url):
            raise ContentError("Inserisci un indirizzo web valido che inizi con https:// (massimo 2000 caratteri).")
        return {"url": url}

    def is_complete(self, content: dict) -> bool:
        return valid_url(content.get("url") or "")

    def public_response(self, content: dict, *, slug: str) -> Response:
        return RedirectResponse(content["url"], status_code=302, headers={"Cache-Control": "no-store"})

    def editor_html(self, content: dict | None) -> str:
        value = esc((content or {}).get("url", ""))
        return f"""
        <label for="link-url">Indirizzo a cui porta il QR</label>
        <input id="link-url" class="input" name="link_url" value="{value}" placeholder="https://..." inputmode="url">
        <p class="p" style="font-size:14px">Il sito, la pagina Instagram, la prenotazione online: quello che vuoi.</p>
        """
