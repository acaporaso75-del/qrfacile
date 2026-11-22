"""Common contract of the content types a module QR can show."""
from __future__ import annotations

from typing import Any, Mapping, Protocol

from fastapi.responses import Response


class ContentError(ValueError):
    """Invalid customer input; the message is Italian and safe to show."""


class ContentType(Protocol):
    key: str
    label: str

    def parse(
        self,
        form: Mapping[str, str],
        files: Mapping[str, Any],
        previous: dict | None,
        *,
        qr_item_id: int,
    ) -> dict: ...

    def public_response(self, content: dict, *, slug: str) -> Response: ...

    def editor_html(self, content: dict | None) -> str: ...


def read_limited(upload: Any, max_bytes: int) -> bytes | None:
    """Read at most max_bytes + 1 bytes; None when the upload is too big."""
    data = upload.file.read(max_bytes + 1)
    if len(data) > max_bytes:
        return None
    return data
