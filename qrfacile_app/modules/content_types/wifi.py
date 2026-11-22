"""Wi-Fi: a page with network name and password (a web page cannot join a network).

The customer area also offers a static "direct Wi-Fi" QR (WIFI: payload) that
joins automatically but cannot be changed after printing.
"""
from __future__ import annotations

from qrfacile_app.modules.content_types.base import ContentError
from qrfacile_app.modules.content_types.page import field, public_page, text
from qrfacile_app.ui_shell import esc

SECURITY = {"WPA": "WPA/WPA2/WPA3 (la più comune)", "WEP": "WEP (vecchia)", "nopass": "Rete aperta, senza password"}


def _escape(value: str) -> str:
    for char in ("\\", ";", ",", ":", '"'):
        value = value.replace(char, "\\" + char)
    return value


def wifi_qr_payload(content: dict) -> str:
    """Standard Wi-Fi QR payload understood by iOS and Android cameras."""
    payload = f"WIFI:T:{content['security']};S:{_escape(content['ssid'])};"
    if content["security"] != "nopass":
        payload += f"P:{_escape(content['password'])};"
    return payload + ";"


class WifiType:
    key = "wifi"
    label = "Wi-Fi"

    def parse(self, form, files, previous, *, qr_item_id):
        ssid = text(form, "wifi_ssid", 32)
        network_key = str(form.get("wifi_password") or "")[:63]
        security = str(form.get("wifi_security") or "WPA")
        if security not in SECURITY:
            raise ContentError("Tipo di protezione non valido.")
        if not ssid:
            raise ContentError("Inserisci il nome della rete Wi-Fi.")
        if any(ord(ch) < 32 for ch in network_key):
            raise ContentError("La password contiene caratteri non validi.")
        if security == "nopass":
            network_key = ""
        elif len(network_key) < (5 if security == "WEP" else 8):
            raise ContentError("La password Wi-Fi è troppo corta (almeno 8 caratteri).")
        return {"ssid": ssid, "password": network_key, "security": security}

    def is_complete(self, content: dict) -> bool:
        return bool(content.get("ssid"))

    def public_response(self, content: dict, *, slug: str):
        password = (
            f'<p>Password</p><p class="big">{esc(content["password"])}</p>'
            if content.get("password") else "<p>Rete aperta: non serve la password.</p>"
        )
        inner = (
            "<h1>Wi-Fi</h1><p>Nome della rete</p>"
            f'<p class="big">{esc(content["ssid"])}</p>{password}'
            "<p>Apri le impostazioni Wi-Fi del telefono, scegli questa rete e inserisci la password.</p>"
        )
        return public_page(f"Wi-Fi {content['ssid']}", inner, slug=slug)

    def editor_html(self, content: dict | None) -> str:
        content = content or {}
        options = "".join(
            f'<option value="{k}"{" selected" if content.get("security", "WPA") == k else ""}>{esc(v)}</option>'
            for k, v in SECURITY.items()
        )
        return (
            field("wifi_ssid", "Nome della rete (SSID)", content.get("ssid", ""), maxlength=32, prefix="wf")
            + field("wifi_password", "Password", content.get("password", ""), maxlength=63, prefix="wf")
            + f'<div><label for="wf-security">Protezione</label><select id="wf-security" name="wifi_security">{options}</select></div>'
            + '<p class="muted" style="font-size:14px">Il QR apre una pagina con nome rete e password. '
            "Dopo il salvataggio puoi scaricare anche un “QR Wi-Fi diretto” che collega in automatico "
            "(ma non si può modificare dopo la stampa).</p>"
        )
