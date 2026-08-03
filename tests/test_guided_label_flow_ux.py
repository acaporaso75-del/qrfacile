from pathlib import Path
from io import BytesIO

from PIL import Image

from qrfacile_app import wine_images_ui

ROOT = Path(__file__).resolve().parents[1]


def test_all_seven_steps_and_expected_ctas_are_visible():
    flow = (ROOT / "qrfacile_app" / "guided_flow.py").read_text(encoding="utf-8")
    compliance = (ROOT / "qrfacile_app" / "wine_compliance_ui.py").read_text(encoding="utf-8")
    hub = (ROOT / "qrfacile_app" / "wine_hub_ui.py").read_text(encoding="utf-8")
    for label in ("Dati vino", "Immagini", "Ingredienti e allergeni", "Valori nutrizionali", "Riciclabilità", "Controllo finale", "Preview e pubblicazione"):
        assert label in flow
    for cta in ("Salva e continua", "Salva", "Indietro", "Apri preview"):
        assert cta in compliance
    for cta in ("Etichetta pronta per la pubblicazione", "Continua compilazione", "Apri pagina pubblica", "Scarica QR"):
        assert cta in hub


def test_unsaved_changes_and_field_anchors_exist():
    source = (ROOT / "qrfacile_app" / "wine_compliance_ui.py").read_text(encoding="utf-8")
    assert "beforeunload" in source
    for anchor in ('id="ingredienti"', 'id="nutrizione"', 'id="riciclabilita"', 'id="controllo-finale"', 'id="pubblicazione"'):
        assert anchor in source


def test_upload_directory_is_configurable_and_readability_is_checked():
    source = (ROOT / "qrfacile_app" / "wine_images_ui.py").read_text(encoding="utf-8")
    storage = (ROOT / "qrfacile_app" / "services" / "storage.py").read_text(encoding="utf-8")
    assert 'os.getenv("UPLOADS_DIR")' in storage
    assert "target.is_file()" in storage
    assert "os.access" in storage
    assert "cur.rowcount != 1" in source


def test_image_upload_creates_all_consistent_readable_results(tmp_path, monkeypatch):
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    content = BytesIO()
    Image.new("RGB", (80, 120), (120, 30, 60)).save(content, format="PNG")
    paths = wine_images_ui._save_images(33, "front", content.getvalue(), ".png")
    assert set(paths) == {"img_original", "img_optimized", "img_thumb"}
    for relative in paths.values():
        saved = tmp_path / relative
        assert saved.is_file()
        assert saved.stat().st_size > 0


def test_preview_and_publication_keep_distinct_routes_and_states():
    public = (ROOT / "qrfacile_app" / "public.py").read_text(encoding="utf-8")
    secure = (ROOT / "qrfacile_app" / "secure_publish_ui.py").read_text(encoding="utf-8")
    assert '@router.get("/preview/{slug}"' in public
    assert '@router.get("/e/{slug}"' in public
    assert "if not preview and status != \"attiva\"" in public
    assert 'action="wine_published"' in secure
    assert 'action="wine_unpublished"' in secure
