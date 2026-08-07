from __future__ import annotations

import pytest

from qrfacile_app import main


def test_required_router_import_failure_stops_application(monkeypatch):
    def fail_import(_module_path):
        raise ImportError("simulated required router failure")

    monkeypatch.setattr(main, "import_module", fail_import)

    with pytest.raises(RuntimeError, match="router obbligatorio"):
        main.include_router_safe("qrfacile_app.auth_routes")


def test_optional_router_import_failure_is_logged_and_skipped(monkeypatch, caplog):
    def fail_import(_module_path):
        raise ImportError("simulated optional router failure")

    monkeypatch.setattr(main, "import_module", fail_import)

    main.include_router_safe("qrfacile_app.guide_pages")

    assert "Router opzionale non caricato" in caplog.text
