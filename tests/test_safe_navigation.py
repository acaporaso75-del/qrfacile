from pathlib import Path

import pytest

from qrfacile_app.navigation_security import safe_local_path


@pytest.mark.parametrize("value", [
    "https://evil.test/path", "//evil.test/path", "/\\evil.test", "\\evil.test",
    "/%2f%2fevil.test", "/%5cevil.test", "/ok\r\nLocation: https://evil.test",
])
def test_unsafe_redirect_targets_fall_back(value):
    assert safe_local_path(value) == "/app/dashboard"


def test_internal_paths_preserve_queries_and_fragments():
    assert safe_local_path("/app/wine/7?tab=export#qr") == "/app/wine/7?tab=export#qr"


def test_user_controlled_navigation_uses_shared_guard_and_html_escaping():
    root = Path(__file__).resolve().parents[1] / "qrfacile_app"
    context = (root / "context_ui.py").read_text(encoding="utf-8")
    collaboration = (root / "collaboration_management_ui.py").read_text(encoding="utf-8")
    printing = (root / "send_print.py").read_text(encoding="utf-8")
    assert context.count("safe_local_path(next_url)") == 2
    assert "url = safe_local_path(url)" in collaboration
    assert "RedirectResponse(safe_local_path(back)" in printing
    assert 'value="{esc(back)}"' in printing
    assert 'value="{esc(slug)}"' in printing
