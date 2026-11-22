"""Galleria: up to 12 photos and a few video links on one page."""
from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from fastapi.responses import FileResponse
from PIL import Image

from qrfacile_app.modules.content_types.base import ContentError, read_limited
from qrfacile_app.modules.content_types.link import valid_url
from qrfacile_app.modules.content_types.page import field, public_page, text
from qrfacile_app.services.storage import get_uploads_dir
from qrfacile_app.ui_shell import esc

MAX_IMAGES = 12
MAX_VIDEOS = 4
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
UPLOAD_SLOTS = 12


def _save_image(upload, qr_item_id: int) -> str:
    data = read_limited(upload, MAX_IMAGE_BYTES)
    if data is None:
        raise ContentError("Una foto supera i 5 MB.")
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = (probe.format or "").upper()
        width, height = probe.size
        probe.verify()
    except Exception as exc:
        raise ContentError("Le foto devono essere immagini JPG, PNG o WebP.") from exc
    if fmt not in ("JPEG", "PNG", "WEBP"):
        raise ContentError("Le foto devono essere immagini JPG, PNG o WebP.")
    if width * height > MAX_IMAGE_PIXELS:
        raise ContentError("Una foto è troppo grande: usa immagini sotto i 5000 × 5000 pixel.")
    image = Image.open(io.BytesIO(data))
    image.thumbnail((1600, 1600))
    image = image.convert("RGB")
    digest = hashlib.sha256(data).hexdigest()[:16]
    relative = f"modules/link/{int(qr_item_id)}/img-{digest}.png"
    target = Path(get_uploads_dir()) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=True)
    return relative


class GalleryType:
    key = "gallery"
    label = "Galleria foto e video"

    def parse(self, form, files, previous, *, qr_item_id):
        title = text(form, "gallery_title", 80)
        if not title:
            raise ContentError("Inserisci il titolo della galleria.")
        description = str(form.get("gallery_text") or "").strip()[:600]
        images = list((previous or {}).get("images") or [])
        images = [img for index, img in enumerate(images, start=1) if form.get(f"gallery_remove_{index}") != "on"]
        uploads = [files.get(f"gallery_image_{i}") for i in range(1, UPLOAD_SLOTS + 2)]
        uploads = [u for u in uploads if u is not None and getattr(u, "filename", "")]
        if len(images) + len(uploads) > MAX_IMAGES:
            raise ContentError(f"Puoi avere al massimo {MAX_IMAGES} foto.")
        for upload in uploads:
            saved = _save_image(upload, qr_item_id)
            if saved not in images:
                images.append(saved)
        videos = []
        for index in range(1, MAX_VIDEOS + 1):
            url = text(form, f"gallery_video_{index}", 2000)
            if not url:
                continue
            if not valid_url(url):
                raise ContentError("Link video non valido: usa un indirizzo che inizia con https://")
            videos.append(url)
        return {"title": title, "text": description, "images": images, "videos": videos}

    def is_complete(self, content: dict) -> bool:
        return bool(content.get("title")) and bool(content.get("images") or content.get("videos"))

    def files(self, content: dict) -> set[str]:
        return set(content.get("images") or [])

    def asset_response(self, content: dict, name: str):
        match = re.fullmatch(r"img-(\d{1,2})", name or "")
        images = content.get("images") or []
        if not match or not 1 <= int(match.group(1)) <= len(images):
            return None
        relative = images[int(match.group(1)) - 1]
        path = Path(get_uploads_dir()) / relative
        if ".." in relative or not path.is_file():
            return None
        return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    def public_response(self, content: dict, *, slug: str):
        photos = "".join(
            f'<img src="/d/{esc(slug)}/a/img-{index}" alt="Foto {index} di {esc(content["title"])}" loading="lazy">'
            for index in range(1, len(content.get("images") or []) + 1)
        )
        videos = "".join(
            f'<a class="button" href="{esc(url)}" rel="noopener">Guarda il video {index}</a>'
            for index, url in enumerate(content.get("videos") or [], start=1)
        )
        text_html = f'<p class="text">{esc(content["text"])}</p>' if content.get("text") else ""
        inner = f'<h1>{esc(content["title"])}</h1>{text_html}<div class="grid">{photos}</div>{videos}'
        return public_page(content["title"], inner, slug=slug)

    def editor_html(self, content: dict | None) -> str:
        content = content or {}
        current = "".join(
            f'<div style="display:flex;gap:10px;align-items:center">'
            f'<input type="checkbox" id="gl-remove-{i}" name="gallery_remove_{i}" value="on">'
            f'<label for="gl-remove-{i}">Togli la foto {i}</label></div>'
            for i in range(1, len(content.get("images") or []) + 1)
        )
        videos = list(content.get("videos") or [])
        video_fields = "".join(
            field(f"gallery_video_{i}", f"Link video {i} (YouTube, Vimeo...)", videos[i - 1] if i <= len(videos) else "",
                  maxlength=2000, prefix="gl")
            for i in range(1, MAX_VIDEOS + 1)
        )
        return (
            field("gallery_title", "Titolo (obbligatorio)", content.get("title", ""), maxlength=80, prefix="gl")
            + '<div><label for="gl-text">Testo breve (facoltativo)</label>'
            + f'<textarea id="gl-text" class="input" name="gallery_text" maxlength="600" rows="3">{esc(content.get("text", ""))}</textarea></div>'
            + current
            + '<div><label for="gl-image-1">Aggiungi foto (JPG, PNG o WebP fino a 5 MB, massimo 12 in tutto)</label>'
            + '<input id="gl-image-1" class="input" type="file" name="gallery_image_1" accept="image/png,image/jpeg,image/webp"></div>'
            + '<div><label for="gl-image-2">Altra foto</label>'
            + '<input id="gl-image-2" class="input" type="file" name="gallery_image_2" accept="image/png,image/jpeg,image/webp"></div>'
            + '<div><label for="gl-image-3">Altra foto</label>'
            + '<input id="gl-image-3" class="input" type="file" name="gallery_image_3" accept="image/png,image/jpeg,image/webp"></div>'
            + video_fields
        )
