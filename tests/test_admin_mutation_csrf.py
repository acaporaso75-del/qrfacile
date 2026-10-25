from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sensitive_admin_and_compliance_mutations_require_csrf_or_same_origin():
    expected_minimum = {
        "admin_credits_ui.py": 1,
        "admin_home_ui.py": 1,
        "admin_override_requests_ui.py": 2,
        "admin_payouts_ui.py": 2,
        "ai_registry_ui.py": 1,
        "ai_review_ui.py": 1,
        "compliance_incidents_ui.py": 2,
        "compliance_ui.py": 1,
        "privacy_requests_ui.py": 1,
    }
    for filename, minimum in expected_minimum.items():
        source = (ROOT / "qrfacile_app" / filename).read_text(encoding="utf-8")
        assert "from qrfacile_app.csrf_core import require_csrf_or_same_origin" in source
        assert source.count("require_csrf_or_same_origin(request)") >= minimum
