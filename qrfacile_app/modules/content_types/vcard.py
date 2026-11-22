"""vCard: scanning the QR offers to save the contact in the phone's address book."""
from __future__ import annotations

import re

from fastapi.responses import Response

from qrfacile_app.modules.content_types.base import ContentError
from qrfacile_app.modules.content_types.link import valid_url
from qrfacile_app.modules.content_types.page import field, text

FIELDS = (
    ("vcard_name", "name", "Nome e cognome (obbligatorio)", 80),
    ("vcard_org", "org", "Azienda", 80),
    ("vcard_title", "title", "Ruolo", 80),
    ("vcard_phone", "phone", "Telefono", 30),
    ("vcard_email", "email", "Email", 120),
    ("vcard_website", "website", "Sito web", 300),
    ("vcard_address", "address", "Indirizzo", 160),
)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")


class VCardType:
    key = "vcard"
    label = "Biglietto da visita"

    def parse(self, form, files, previous, *, qr_item_id):
        raw_name = str(form.get("vcard_name") or "")
        if "\r" in raw_name or "\n" in raw_name:
            raise ContentError("Il nome non può andare a capo.")
        content = {key: text(form, form_key, limit) for form_key, key, _label, limit in FIELDS}
        if not content["name"]:
            raise ContentError("Inserisci nome e cognome.")
        if content["phone"]:
            content["phone"] = re.sub(r"[^\d+]", "", content["phone"])
            if not re.fullmatch(r"\+?\d{6,20}", content["phone"]):
                raise ContentError("Numero di telefono non valido.")
        if content["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", content["email"]):
            raise ContentError("Email non valida.")
        if content["website"] and not valid_url(content["website"]):
            raise ContentError("Sito non valido: usa un indirizzo che inizia con https://")
        return content

    def is_complete(self, content: dict) -> bool:
        return bool(content.get("name"))

    def public_response(self, content: dict, *, slug: str) -> Response:
        lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{_escape(content['name'])}", f"N:{_escape(content['name'])};;;;"]
        if content.get("org"):
            lines.append(f"ORG:{_escape(content['org'])}")
        if content.get("title"):
            lines.append(f"TITLE:{_escape(content['title'])}")
        if content.get("phone"):
            lines.append(f"TEL;TYPE=CELL:{content['phone']}")
        if content.get("email"):
            lines.append(f"EMAIL:{content['email']}")
        if content.get("website"):
            lines.append(f"URL:{content['website']}")
        if content.get("address"):
            lines.append(f"ADR;TYPE=WORK:;;{_escape(content['address'])};;;;")
        lines.append("END:VCARD")
        filename = re.sub(r"[^a-z0-9]+", "-", content["name"].lower()).strip("-")[:40] or "contatto"
        return Response(
            "\r\n".join(lines) + "\r\n",
            media_type="text/vcard",
            headers={"Content-Disposition": f'inline; filename="{filename}.vcf"', "Cache-Control": "no-store"},
        )

    def editor_html(self, content: dict | None) -> str:
        content = content or {}
        return "".join(
            field(form_key, label, content.get(key, ""), maxlength=limit, prefix="vc",
                  type_="email" if key == "email" else "text")
            for form_key, key, label, limit in FIELDS
        ) + '<p class="muted" style="font-size:14px">Chi inquadra il QR salva il contatto in rubrica con un tocco.</p>'
