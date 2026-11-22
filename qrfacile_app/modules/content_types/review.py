"""Recensioni: the QR opens the Google review form of the business."""
from __future__ import annotations

import re

from fastapi.responses import RedirectResponse

from qrfacile_app.modules.content_types.base import ContentError
from qrfacile_app.modules.content_types.link import valid_url
from qrfacile_app.modules.content_types.page import field, text

WRITE_REVIEW = "https://search.google.com/local/writereview?placeid="


class ReviewType:
    key = "review"
    label = "Recensioni"

    def parse(self, form, files, previous, *, qr_item_id):
        place_id = text(form, "review_place_id", 200)
        url = text(form, "review_url", 2000)
        if place_id:
            if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", place_id):
                raise ContentError("Place ID non valido: copialo da Google senza spazi.")
            return {"place_id": place_id, "url": WRITE_REVIEW + place_id}
        if url:
            if not valid_url(url):
                raise ContentError("Indirizzo non valido: usa il link di recensione che inizia con https://")
            return {"place_id": "", "url": url}
        raise ContentError("Inserisci il link per le recensioni oppure il Place ID di Google.")

    def is_complete(self, content: dict) -> bool:
        return valid_url(content.get("url") or "")

    def public_response(self, content: dict, *, slug: str):
        return RedirectResponse(content["url"], status_code=302, headers={"Cache-Control": "no-store"})

    def editor_html(self, content: dict | None) -> str:
        content = content or {}
        return (
            field("review_url", "Link per lasciare una recensione", "" if content.get("place_id") else content.get("url", ""),
                  hint="Da Google Business Profile: “Chiedi recensioni” → copia il link.", maxlength=2000, prefix="rv")
            + field("review_place_id", "Oppure Place ID di Google", content.get("place_id", ""),
                    hint="In alternativa al link. Se compili entrambi, vale il Place ID.", prefix="rv")
        )
