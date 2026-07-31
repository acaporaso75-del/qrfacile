from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_page_rechecks_server_side_compliance_gate():
    source = (ROOT / "qrfacile_app" / "public.py").read_text(encoding="utf-8")

    assert "run_explainable_wine_compliance(compliance_payload)" in source
    assert "_public_gate_allows(status, public_missing, compliance_report)" in source
    assert 'bool(compliance_report.get("publishable"))' in source
    assert "QR non conforme o incompleto" in source
