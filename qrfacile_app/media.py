# /opt/qrfacile/qrfacile_app/media.py
import os
import io
import time
from typing import Dict

from PIL import Image, ImageFile
from fastapi import UploadFile

from qrfacile_app.services.storage import get_uploads_dir

UPLOADS_DIR = str(get_uploads_dir())

MAX_UPLOAD_BYTES = 5 * 1024 * 1024          # 5 MB
MAX_IMAGE_PIXELS = 40_000_000               # anti decompression bomb
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}

ImageFile.LOAD_TRUNCATED_IMAGES = False
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _ensure_uploads_dir():
    os.makedirs(UPLOADS_DIR, exist_ok=True)


def _read_limited(upload: UploadFile, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes | None:
    """
    Legge massimo max_bytes+1.
    Se supera il limite ritorna None.
    """
    try:
        data = upload.file.read(max_bytes + 1)
    except Exception:
        return b""

    if not data:
        return b""

    if len(data) > max_bytes:
        return None

    return data


def _validate_image(data: bytes) -> tuple[Image.Image, str]:
    """
    Verifica che il file sia davvero un'immagine supportata.
    Riapre l'immagine dopo verify() perché PIL invalida l'oggetto verificato.
    """
    if not data or len(data) < 64:
        raise ValueError("File vuoto o troppo piccolo")

    try:
        probe = Image.open(io.BytesIO(data))
        fmt = (probe.format or "").upper()
        probe.verify()

        if fmt not in ALLOWED_FORMATS:
            raise ValueError("Formato non supportato")

        img = Image.open(io.BytesIO(data))
        img.load()

        if img.format and img.format.upper() not in ALLOWED_FORMATS:
            raise ValueError("Formato non supportato")

        return img, fmt

    except Image.DecompressionBombError:
        raise ValueError("Immagine troppo grande")
    except Exception as exc:
        raise ValueError("Immagine non valida") from exc


def _normalize_for_logo(img: Image.Image) -> Image.Image:
    """
    Normalizza logo:
    - mantiene trasparenza se PNG/WebP con alpha;
    - ridimensiona massimo 1024 px lato lungo;
    - rimuove metadata risalvando da immagine pulita.
    """
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    w, h = img.size
    max_side = max(w, h)

    if max_side > 1024:
        scale = 1024 / max_side
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        img = img.resize(new_size)

    return img


def _make_thumb(img: Image.Image) -> Image.Image:
    thumb = img.copy()

    if thumb.mode not in ("RGB", "RGBA"):
        thumb = thumb.convert("RGBA")

    thumb.thumbnail((420, 240))
    return thumb


def process_logo(upload: UploadFile, winery_id: int) -> Dict[str, str]:
    """
    Processa logo cantina in modo sicuro:
    - accetta solo jpeg/png/webp;
    - verifica bytes reali;
    - limita peso e pixel;
    - ridimensiona;
    - salva file con nome generato;
    - rimuove metadata;
    - produce logo PNG e thumbnail WebP.

    Ritorna:
      {"logo_path": "...", "thumb_path": "..."}
    """
    _ensure_uploads_dir()

    ctype = (upload.content_type or "").strip().lower()

    if ctype and ctype not in ALLOWED_CONTENT_TYPES:
        raise ValueError("Content-Type non supportato")

    data = _read_limited(upload)

    if data is None:
        raise ValueError("File troppo grande")

    if not data:
        raise ValueError("File vuoto")

    img, _fmt = _validate_image(data)

    img = _normalize_for_logo(img)
    thumb = _make_thumb(img)

    ts = int(time.time())

    logo_filename = f"logo_winery_{int(winery_id)}_{ts}.png"
    thumb_filename = f"logo_winery_{int(winery_id)}_{ts}_thumb.webp"

    logo_path_abs = os.path.join(UPLOADS_DIR, logo_filename)
    thumb_path_abs = os.path.join(UPLOADS_DIR, thumb_filename)

    # Salva logo pulito. PNG mantiene eventuale trasparenza.
    if img.mode == "RGBA":
        img.save(logo_path_abs, format="PNG", optimize=True)
    else:
        img = img.convert("RGB")
        img.save(logo_path_abs, format="PNG", optimize=True)

    # Thumbnail WebP.
    if thumb.mode == "RGBA":
        thumb.save(thumb_path_abs, format="WEBP", quality=84, method=6)
    else:
        thumb = thumb.convert("RGB")
        thumb.save(thumb_path_abs, format="WEBP", quality=84, method=6)

    try:
        os.chmod(logo_path_abs, 0o644)
        os.chmod(thumb_path_abs, 0o644)
    except Exception:
        pass

    return {
        "logo_path": logo_filename,
        "thumb_path": thumb_filename,
    }
