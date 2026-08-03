import asyncio
from io import BytesIO

from PIL import Image
from qrfacile_app import public, uploads_routes, wine_images_ui
from qrfacile_app.services.storage import versioned_upload_url


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
            wine_id, kind, original, optimized, thumb, updated = params
            previous = self.state.get((wine_id, kind), {}).get("updated_at", 0)
            self.state[(wine_id, kind)] = {
                "img_original": original,
                "img_optimized": optimized,
                "img_thumb": thumb,
                "updated_at": max(updated, previous + 1),
            }
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
    for relative in (persisted["img_original"], persisted["img_optimized"], persisted["img_thumb"]):
        disk = tmp_path / relative
        assert disk.is_file() and disk.stat().st_size > 0
        served = uploads_routes._serve_upload(relative)
        assert served.status_code == 200
        assert served.path == str(disk)

    html = wine_images_ui._image_card(41, "front", {**persisted, "updated_at": 123})
    assert '<img src="/uploads/wine_assets/41/front/thumb.webp?v=123"' in html
    assert uploads_routes._serve_upload("wine_assets/41/front/thumb.webp").status_code == 200


def test_replacement_changes_only_version_and_public_preview_html(tmp_path, monkeypatch):
    state = {}
    timestamps = iter((100, 200, 300))
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    monkeypatch.setattr(wine_images_ui, "pg", lambda: Connection(state))
    monkeypatch.setattr(wine_images_ui, "require_any_role", lambda *_args, **_kwargs: {"id": 1, "role": "winery"})
    monkeypatch.setattr(wine_images_ui, "now", lambda: next(timestamps))

    def upload(kind, color):
        content = BytesIO()
        Image.new("RGB", (160, 240), color).save(content, format="PNG")
        return asyncio.run(wine_images_ui.images_upload(object(), 41, kind, AsyncUpload(content.getvalue())))

    assert upload("front", (200, 10, 10)).status_code == 303
    first = dict(state[(41, "front")])
    physical_path = tmp_path / first["img_optimized"]
    first_bytes = physical_path.read_bytes()
    first_url = versioned_upload_url(first["img_optimized"], first["updated_at"])
    assert first_url.endswith("/optimized.jpg?v=100")

    assert upload("front", (10, 200, 10)).status_code == 303
    second = dict(state[(41, "front")])
    second_url = versioned_upload_url(second["img_optimized"], second["updated_at"])
    assert second["updated_at"] == 200
    assert second["img_optimized"] == first["img_optimized"]
    assert second_url.endswith("/optimized.jpg?v=200") and second_url != first_url
    assert physical_path.read_bytes() != first_bytes
    assert uploads_routes._serve_upload(second["img_optimized"], versioned=True).status_code == 200
    assert uploads_routes._serve_upload(second["img_optimized"], versioned=True).headers["cache-control"] == "public, max-age=31536000, immutable"

    assert upload("back", (10, 10, 200)).status_code == 303
    back = dict(state[(41, "back")])
    rows = [dict(second, kind="front"), dict(back, kind="back")]
    label_html = public._label_images_html(rows, "Test")
    assert second_url in label_html
    assert versioned_upload_url(back["img_optimized"], 300) in label_html
    assert "Fronte etichetta" in label_html and "Retro etichetta" in label_html

    calls = []
    monkeypatch.setattr(public, "_render_label_page", lambda request, slug, *, preview: calls.append((slug, preview)) or label_html)
    assert second_url in public.public_label(object(), "test-slug")
    assert second_url in public.preview_label(object(), "test-slug")
    assert calls == [("test-slug", False), ("test-slug", True)]
