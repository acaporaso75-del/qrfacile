from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_recycling_middleware_targets_public_and_preview_labels():
    text = (ROOT / "qrfacile_app" / "public_recycling_catalog_middleware.py").read_text(encoding="utf-8")
    assert 'PUBLIC_LABEL_PATH = re.compile(r"^/(?:e|preview)/[^/]+/?$")' in text
    assert "PublicRecyclingCatalogMiddleware" in text
    assert "RECYCLING_CATALOG" in text
    assert "CATALOG_VERSION" in text
    assert "CATALOG_SOURCE" in text


def test_public_recycling_widget_marks_known_and_custom_codes():
    text = (ROOT / "qrfacile_app" / "public_recycling_catalog_middleware.py").read_text(encoding="utf-8")
    assert "Codice verificato nel catalogo" in text
    assert "Codice personalizzato da verificare" in text
    assert "Le modalità di raccolta vanno verificate" in text
    assert ".recycleItem" in text
    assert ".materialCode" in text
    assert ".recycleGrid" in text


def test_public_recycling_middleware_is_registered():
    main = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    assert "from qrfacile_app.public_recycling_catalog_middleware import PublicRecyclingCatalogMiddleware" in main
    assert "app.add_middleware(PublicRecyclingCatalogMiddleware)" in main
