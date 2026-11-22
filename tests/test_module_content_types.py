"""Content types of QRFacile Link: Link, PDF, Mini-pagina."""
from __future__ import annotations

import io
import re

import pytest
from PIL import Image

from qrfacile_app.modules.content_types import CONTENT_TYPES, ContentError, get_type
from qrfacile_app.modules.content_types import pdf as pdf_type


class _Upload:
    def __init__(self, data: bytes, filename: str = "listino.pdf"):
        self.file = io.BytesIO(data)
        self.filename = filename


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_type, "get_uploads_dir", lambda: tmp_path)
    from qrfacile_app.modules.content_types import minipage

    monkeypatch.setattr(minipage, "get_uploads_dir", lambda: tmp_path)
    return tmp_path


def _pdf_bytes(size: int = 2000) -> bytes:
    head = b"%PDF-1.4\n"
    return head + b"0" * (size - len(head))


def test_registry_starts_with_the_three_original_types():
    assert list(CONTENT_TYPES)[:3] == ["link", "pdf", "minipage"]
    with pytest.raises(KeyError):
        get_type("video")


def test_link_rejects_javascript_and_long_urls():
    link = get_type("link")
    assert link.parse({"link_url": "https://example.com/x"}, {}, None, qr_item_id=1) == {"url": "https://example.com/x"}
    for bad in ("javascript:alert(1)", "ftp://x.test", "", "https://x.test/" + "a" * 2000):
        with pytest.raises(ContentError):
            link.parse({"link_url": bad}, {}, None, qr_item_id=1)


def test_link_public_response_redirects_without_cache():
    response = get_type("link").public_response({"url": "https://example.com"}, slug="AAA")
    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com"
    assert response.headers["cache-control"] == "no-store"


def test_pdf_rejects_non_pdf_and_over_10mb(uploads):
    pdf = get_type("pdf")
    with pytest.raises(ContentError):
        pdf.parse({}, {"pdf_file": _Upload(b"<html><script>x</script></html>" * 10, "x.pdf")}, None, qr_item_id=1)
    with pytest.raises(ContentError):
        pdf.parse({}, {"pdf_file": _Upload(_pdf_bytes(10 * 1024 * 1024 + 1))}, None, qr_item_id=1)
    with pytest.raises(ContentError):
        pdf.parse({}, {"pdf_file": None}, None, qr_item_id=1)
    content = pdf.parse({}, {"pdf_file": _Upload(_pdf_bytes(), "Listino 2027 <x>.pdf")}, None, qr_item_id=7)
    assert content["size"] == 2000 and len(content["sha256"]) == 64
    assert content["file"].startswith("modules/link/7/") and content["file"].endswith(".pdf")
    assert (uploads / content["file"]).read_bytes()[:5] == b"%PDF-"
    assert "<" not in content["name"] and content["name"].endswith(".pdf")


def test_pdf_keeps_previous_file_when_none_uploaded(uploads):
    pdf = get_type("pdf")
    first = pdf.parse({}, {"pdf_file": _Upload(_pdf_bytes())}, None, qr_item_id=3)
    again = pdf.parse({}, {"pdf_file": None}, first, qr_item_id=3)
    assert again == first


def test_pdf_public_response_headers(uploads):
    pdf = get_type("pdf")
    content = pdf.parse({}, {"pdf_file": _Upload(_pdf_bytes(), "menu.pdf")}, None, qr_item_id=4)
    response = pdf.public_response(content, slug="AAA")
    assert response.media_type == "application/pdf"
    assert response.headers["content-disposition"].startswith("inline")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def _minipage_form(**overrides):
    form = {
        "minipage_title": "Bottega Rossi",
        "minipage_text": "Pane e dolci dal 1952",
        "minipage_button_kind_1": "call", "minipage_button_value_1": "+39 0824 123456",
        "minipage_button_kind_2": "whatsapp", "minipage_button_value_2": "+39 333 1234567",
        "minipage_button_kind_3": "email", "minipage_button_value_3": "info@example.test",
        "minipage_button_kind_4": "map", "minipage_button_value_4": "Via Roma 1, Benevento",
        "minipage_button_kind_5": "site", "minipage_button_value_5": "https://example.test",
    }
    form.update(overrides)
    return form


def test_minipage_limits_and_escaping(uploads):
    mp = get_type("minipage")
    for bad in (
        _minipage_form(minipage_title="x" * 81),
        _minipage_form(minipage_text="x" * 601),
        _minipage_form(minipage_title=""),
        _minipage_form(minipage_button_kind_5="site", minipage_button_value_5="javascript:alert(1)"),
        _minipage_form(minipage_button_kind_6="instagram", minipage_button_value_6="https://instagram.com/x",
                       minipage_button_kind_7="facebook", minipage_button_value_7="https://facebook.com/x"),
        _minipage_form(minipage_button_kind_1="telegram"),
    ):
        with pytest.raises(ContentError):
            mp.parse(bad, {}, None, qr_item_id=1)
    content = mp.parse(_minipage_form(minipage_text="<script>alert(1)</script>"), {}, None, qr_item_id=1)
    html = mp.public_response(content, slug="AAA").body.decode()
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html
    assert "/segnala/AAA" in html
    assert "<script" not in html.lower()  # no scripts at all on public pages


def test_minipage_button_links(uploads):
    mp = get_type("minipage")
    html = mp.public_response(mp.parse(_minipage_form(), {}, None, qr_item_id=1), slug="AAA").body.decode()
    assert 'href="tel:+390824123456"' in html
    assert 'href="https://wa.me/393331234567"' in html
    assert 'href="mailto:info@example.test"' in html
    assert 'href="https://www.google.com/maps/search/?api=1&amp;query=Via+Roma+1%2C+Benevento"' in html
    assert 'href="https://example.test"' in html


def test_minipage_logo_must_be_a_real_image(uploads):
    mp = get_type("minipage")
    buf = io.BytesIO()
    Image.new("RGB", (120, 120), (20, 120, 110)).save(buf, format="PNG")
    content = mp.parse(_minipage_form(), {"minipage_logo": _Upload(buf.getvalue(), "logo.png")}, None, qr_item_id=9)
    assert content["logo"].startswith("modules/link/9/") and (uploads / content["logo"]).exists()
    with pytest.raises(ContentError):
        mp.parse(_minipage_form(), {"minipage_logo": _Upload(b"not an image" * 20, "logo.png")}, None, qr_item_id=9)


def test_editor_controls_are_labelled():
    control = re.compile(r"<(input|select|textarea)\b([^>]*)>")
    for key, ctype in CONTENT_TYPES.items():
        html = ctype.editor_html(None)
        for match in control.finditer(html):
            attrs = match.group(2)
            if 'type="hidden"' in attrs:
                continue
            ident = re.search(r'id="([^"]+)"', attrs)
            assert "aria-label" in attrs or (ident and f'for="{ident.group(1)}"' in html), (key, attrs[:60])
