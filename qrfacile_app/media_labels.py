import os
import io
from PIL import Image, ImageOps

UPLOADS_DIR = "/opt/qrfacile/uploads"

MAX_ORIGINAL_MB = 20
MAX_ORIGINAL_BYTES = MAX_ORIGINAL_MB * 1024 * 1024

# Dimensioni
OPT_MAX_W = 1600
THUMB_W = 420

def _safe_mkdir(path: str):
    os.makedirs(path, exist_ok=True)

def _to_rgb(img: Image.Image) -> Image.Image:
    # Forza orientamento EXIF e converte a RGB per JPG
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img

def _resize_to_width(img: Image.Image, width: int) -> Image.Image:
    if img.width <= width:
        return img
    ratio = width / float(img.width)
    h = int(img.height * ratio)
    return img.resize((width, h), Image.LANCZOS)

def process_label_image(upload_file, winery_id: int, label_id: int) -> dict:
    """
    Salva:
      - original.jpg (RGB)
      - optimized.jpg (ridimensionata)
      - thumb.webp (piccola, veloce)
    Ritorna path relativi a /uploads.
    """
    # Leggi bytes
    data = upload_file.file.read()
    if not data:
        raise ValueError("File vuoto")
    if len(data) > MAX_ORIGINAL_BYTES:
        raise ValueError(f"File troppo grande (max {MAX_ORIGINAL_MB}MB)")

    # Apri immagine
    try:
        img = Image.open(io.BytesIO(data))
    except Exception:
        raise ValueError("Formato immagine non valido (usa JPG/PNG/WebP)")

    base_rel = f"labels/{int(winery_id)}/{int(label_id)}"
    base_abs = os.path.join(UPLOADS_DIR, base_rel)
    _safe_mkdir(base_abs)

    # ORIGINAL
    img_rgb = _to_rgb(img)
    original_rel = f"{base_rel}/original.jpg"
    original_abs = os.path.join(UPLOADS_DIR, original_rel)
    img_rgb.save(original_abs, format="JPEG", quality=92, optimize=True, progressive=True)

    # OPTIMIZED
    opt = _resize_to_width(img_rgb, OPT_MAX_W)
    optimized_rel = f"{base_rel}/optimized.jpg"
    optimized_abs = os.path.join(UPLOADS_DIR, optimized_rel)
    opt.save(optimized_abs, format="JPEG", quality=88, optimize=True, progressive=True)

    # THUMB (WEBP)
    thumb = _resize_to_width(img_rgb, THUMB_W)
    thumb_rel = f"{base_rel}/thumb.webp"
    thumb_abs = os.path.join(UPLOADS_DIR, thumb_rel)
    thumb.save(thumb_abs, format="WEBP", quality=82, method=6)

    return {
        "label_img_original": original_rel,
        "label_img_optimized": optimized_rel,
        "label_img_thumb": thumb_rel,
    }

