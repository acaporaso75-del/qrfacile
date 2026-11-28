from __future__ import annotations

from io import BytesIO

from fastapi import UploadFile
from PIL import Image

from qrfacile_app.media_labels import process_label_image


def test_label_upload_writes_only_to_configured_staging_directory(tmp_path, monkeypatch):
    staging_uploads = tmp_path / "staging" / "uploads"
    forbidden_production = tmp_path / "production" / "uploads"
    monkeypatch.setenv("UPLOADS_DIR", str(staging_uploads))
    monkeypatch.setenv("APP_ROOT", str(tmp_path / "staging"))

    image_bytes = BytesIO()
    Image.new("RGB", (24, 32), (120, 20, 80)).save(image_bytes, format="PNG")
    upload = UploadFile(filename="label.png", file=BytesIO(image_bytes.getvalue()))

    result = process_label_image(upload, winery_id=4, label_id=9)

    assert set(result) == {
        "label_img_original",
        "label_img_optimized",
        "label_img_thumb",
    }
    assert all((staging_uploads / relative).is_file() for relative in result.values())
    assert not forbidden_production.exists()
