from starlette.requests import Request

from qrfacile_app import export_compat
from qrfacile_app.export_qr_ui import PRESETS


def _request():
    return Request({
        "type": "http", "method": "GET", "scheme": "https", "path": "/app/export/7",
        "headers": [(b"host", b"example.test")], "client": ("127.0.0.1", 1),
    })


def test_legacy_formats_map_to_real_export_presets():
    assert export_compat._legacy_preset("png", 20, 300) == "label_std"
    assert export_compat._legacy_preset("jpg", 25, 600) == "label_pro"
    assert export_compat._legacy_preset("svg", 25, 300) == "vector_svg"
    assert export_compat._legacy_preset("pdf", 25, 600) == "square_pdf"
    assert export_compat._legacy_preset("pdf_a4", 25, 600) == "a4_pdf"
    assert {"vector_svg", "square_pdf"}.issubset(PRESETS)


def test_compat_redirect_uses_supported_parameters_and_encodes_name(monkeypatch):
    monkeypatch.setattr(export_compat, "require_any_role", lambda *_args, **_kwargs: {"id": 1})
    response = export_compat.export_compat(
        _request(), 7, fmt="svg", size_mm=25, dpi=600, name="lotto A&next=//evil.test\r\nX-Test: bad"
    )
    location = response.headers["location"]
    assert location.startswith("/app/wine/7/export/file?preset=vector_svg&name=")
    assert "&next=" not in location
    assert "\r" not in location and "\n" not in location


def test_unknown_legacy_options_fail_to_safe_default():
    assert export_compat._legacy_preset("exe", 9999, 9999) == "label_pro"
