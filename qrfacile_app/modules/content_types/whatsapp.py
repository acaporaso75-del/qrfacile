"""WhatsApp: the QR opens a chat with the business, message already written."""
from __future__ import annotations

import re
from urllib.parse import quote

from fastapi.responses import RedirectResponse

from qrfacile_app.modules.content_types.base import ContentError
from qrfacile_app.modules.content_types.page import field


class WhatsAppType:
    key = "whatsapp"
    label = "WhatsApp"

    def parse(self, form, files, previous, *, qr_item_id):
        number = re.sub(r"\D", "", str(form.get("whatsapp_number") or ""))
        message = str(form.get("whatsapp_message") or "").strip()[:500]
        if not 8 <= len(number) <= 15:
            raise ContentError("Numero WhatsApp non valido: indica prefisso internazionale e numero (es. +39 333...).")
        return {"number": number, "message": message}

    def is_complete(self, content: dict) -> bool:
        return bool(content.get("number"))

    def public_response(self, content: dict, *, slug: str):
        url = f"https://wa.me/{content['number']}"
        if content.get("message"):
            url += "?text=" + quote(content["message"], safe="")
        return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store"})

    def editor_html(self, content: dict | None) -> str:
        content = content or {}
        return (
            field("whatsapp_number", "Numero WhatsApp con prefisso", content.get("number", ""),
                  hint="Esempio: +39 333 123 4567", maxlength=30, prefix="wa")
            + '<div><label for="wa-message">Messaggio già scritto (facoltativo)</label>'
            + f'<textarea id="wa-message" class="input" name="whatsapp_message" maxlength="500" rows="3">'
            + f'{_esc(content.get("message", ""))}</textarea></div>'
        )


def _esc(value: str) -> str:
    from qrfacile_app.ui_shell import esc

    return esc(value)
