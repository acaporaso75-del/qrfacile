from __future__ import annotations

import pytest

from qrfacile_app import main


REVENUE_AND_PUBLISHING_ROUTERS = (
    "qrfacile_app.pricing_ui",
    "qrfacile_app.billing_ui",
    "qrfacile_app.paypal_ui",
    "qrfacile_app.publish_routes",
    "qrfacile_app.export_qr_ui",
    "qrfacile_app.legal_pages",
    "qrfacile_app.legal_acceptance_ui",
    "qrfacile_app.privacy_requests_ui",
    "qrfacile_app.wine_flow_ui",
    "qrfacile_app.wine_hub_ui",
    "qrfacile_app.wine_images_ui",
    "qrfacile_app.wine_compliance_ui",
)


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


@pytest.mark.parametrize("module_path", REVENUE_AND_PUBLISHING_ROUTERS)
def test_revenue_and_publishing_routers_are_mandatory(module_path, monkeypatch):
    assert module_path in main.MANDATORY_ROUTERS

    def fail_import(_module_path):
        raise ImportError("simulated failure")

    monkeypatch.setattr(main, "import_module", fail_import)

    with pytest.raises(RuntimeError, match="router obbligatorio"):
        main.include_router_safe(module_path)
