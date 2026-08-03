import asyncio
from io import BytesIO

from PIL import Image
from qrfacile_app import uploads_routes, wine_images_ui


class AsyncUpload:
    filename = "front.png"
    content_type = "image/png"
    def __init__(self, data): self.data = data
    async def read(self, _limit): return self.data


class Cursor:
    def __init__(self, state): self.state, self.last, self.rowcount = state, "", 0
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, sql, params):
        self.last = " ".join(sql.split()).lower()
        if self.last.startswith("insert into wine_assets"):
            wine_id, kind, original, optimized, thumb, _updated = params
            self.state[(wine_id, kind)] = {"img_original": original, "img_optimized": optimized, "img_thumb": thumb}
            self.rowcount = 1
    def fetchone(self):
        if "from qr_wines" in self.last:
            return {"wine_id": 41, "winery_id": 9, "wine_name": "Test", "winery_name": "Cantina"}
        if "select img_original" in self.last:
            return dict(self.state[(41, "front")])
        return None


class Connection:
    def __init__(self, state): self.state = state
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def cursor(self, **_kwargs): return Cursor(self.state)
    def commit(self): pass
    def rollback(self): pass


def test_real_upload_db_redirect_preview_and_file_response_roundtrip(tmp_path, monkeypatch):
    state = {}
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    monkeypatch.setattr(wine_images_ui, "pg", lambda: Connection(state))
    monkeypatch.setattr(wine_images_ui, "require_any_role", lambda *_args, **_kwargs: {"id": 1, "role": "winery"})
    content = BytesIO()
    Image.new("RGB", (160, 240), (30, 90, 120)).save(content, format="PNG")
    upload = AsyncUpload(content.getvalue())

    response = asyncio.run(wine_images_ui.images_upload(object(), 41, "front", upload))
    assert response.status_code == 303
    assert "Caricato" in response.headers["location"]
    persisted = state[(41, "front")]
    for relative in persisted.values():
        disk = tmp_path / relative
        assert disk.is_file() and disk.stat().st_size > 0
        served = uploads_routes._serve_upload(relative)
        assert served.status_code == 200
        assert served.path == str(disk)

    html = wine_images_ui._image_card(41, "front", {**persisted, "updated_at": 123})
    assert '<img src="/uploads/wine_assets/41/front/thumb.webp?v=123"' in html
    assert uploads_routes._serve_upload("wine_assets/41/front/thumb.webp").status_code == 200
