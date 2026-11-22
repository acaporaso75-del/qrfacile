"""PDF: the QR opens a document (price list, menu, catalogue, manual)."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fastapi.responses import FileResponse, Response

from qrfacile_app.modules.content_types.base import ContentError, read_limited
from qrfacile_app.services.storage import get_uploads_dir
from qrfacile_app.ui_shell import esc

MAX_PDF_BYTES = 10 * 1024 * 1024


def _safe_name(filename: str) -> str:
    stem = Path(filename or "documento.pdf").stem
    stem = re.sub(r"[^A-Za-z0-9 ._-]+", "", stem).strip(" .") or "documento"
    return stem[:80] + ".pdf"


class PdfType:
    key = "pdf"
    label = "PDF"

    def parse(self, form, files, previous, *, qr_item_id):
        upload = files.get("pdf_file")
        if upload is None or not getattr(upload, "filename", ""):
            if previous and previous.get("file"):
                return previous
            raise ContentError("Carica un file PDF.")
        data = read_limited(upload, MAX_PDF_BYTES)
        if data is None:
            raise ContentError("Il PDF supera i 10 MB: riducilo e riprova.")
        if not data.startswith(b"%PDF-"):
            raise ContentError("Il file non è un PDF valido.")
        digest = hashlib.sha256(data).hexdigest()
        relative = f"modules/link/{int(qr_item_id)}/{digest[:16]}.pdf"
        target = Path(get_uploads_dir()) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {"file": relative, "name": _safe_name(upload.filename), "size": len(data), "sha256": digest}

    def is_complete(self, content: dict) -> bool:
        return bool(content.get("file"))

    def files(self, content: dict) -> set[str]:
        return {content["file"]} if content.get("file") else set()

    def public_response(self, content: dict, *, slug: str) -> Response:
        path = Path(get_uploads_dir()) / content["file"]
        if not path.is_file():
            raise FileNotFoundError(content["file"])
        return FileResponse(
            path,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{content.get("name") or "documento.pdf"}"',
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "no-store",
            },
        )

    def editor_html(self, content: dict | None) -> str:
        current = ""
        if content and content.get("file"):
            size_mb = int(content.get("size") or 0) / (1024 * 1024)
            current = f'<p class="p">PDF attuale: <b>{esc(content.get("name") or "")}</b> ({size_mb:.1f} MB). Caricane uno nuovo solo per sostituirlo.</p>'
        return f"""
        {current}
        <label for="pdf-file">File PDF (massimo 10 MB)</label>
        <input id="pdf-file" class="input" type="file" name="pdf_file" accept="application/pdf">
        <p class="p" style="font-size:14px">Listino, menu, catalogo o istruzioni. Quando lo sostituisci il QR resta lo stesso.</p>
        """
