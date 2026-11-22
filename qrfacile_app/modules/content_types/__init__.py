"""Pluggable content types: adding one never requires touching the others."""
from __future__ import annotations

from qrfacile_app.modules.content_types.base import ContentError, ContentType
from qrfacile_app.modules.content_types.event import EventType
from qrfacile_app.modules.content_types.gallery import GalleryType
from qrfacile_app.modules.content_types.link import LinkType
from qrfacile_app.modules.content_types.minipage import MiniPageType
from qrfacile_app.modules.content_types.pdf import PdfType
from qrfacile_app.modules.content_types.review import ReviewType
from qrfacile_app.modules.content_types.vcard import VCardType
from qrfacile_app.modules.content_types.whatsapp import WhatsAppType
from qrfacile_app.modules.content_types.wifi import WifiType

CONTENT_TYPES: dict[str, ContentType] = {
    "link": LinkType(),
    "pdf": PdfType(),
    "minipage": MiniPageType(),
    "vcard": VCardType(),
    "wifi": WifiType(),
    "review": ReviewType(),
    "whatsapp": WhatsAppType(),
    "gallery": GalleryType(),
    "event": EventType(),
}


def get_type(key: str) -> ContentType:
    return CONTENT_TYPES[key]


__all__ = ["CONTENT_TYPES", "ContentError", "ContentType", "get_type"]
