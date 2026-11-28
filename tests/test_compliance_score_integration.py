from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_compliance_score_middleware_is_registered():
    main_text = (ROOT / "qrfacile_app" / "main.py").read_text(encoding="utf-8")
    middleware_text = (
        ROOT / "qrfacile_app" / "compliance_score_middleware.py"
    ).read_text(encoding="utf-8")

    assert "ComplianceScoreMiddleware" in main_text
    assert "app.add_middleware(ComplianceScoreMiddleware)" in main_text
    assert "/api/wines/{wine_id}/compliance-report" in middleware_text
    assert "/app/wine/{wine_id}/compliance-report" in middleware_text


def test_score_widget_is_safe_and_explainable():
    text = (ROOT / "qrfacile_app" / "compliance_score_middleware.py").read_text(
        encoding="utf-8"
    )

    assert "textContent" not in text or "innerHTML" in text
    assert "credentials:'same-origin'" in text
    assert "Revisione umana obbligatoria" in text
    assert "Sono presenti errori bloccanti" in text
    assert "Nessun errore bloccante rilevato" in text
    assert "document.getElementById('qrf-score-widget')" in text


def test_middleware_targets_only_authenticated_wine_compliance_page():
    text = (ROOT / "qrfacile_app" / "compliance_score_middleware.py").read_text(
        encoding="utf-8"
    )

    assert 'r"^/app/wine/(?P<wine_id>\\d+)/compliance/?$"' in text
    assert 'response.status_code != 200' in text
    assert '"text/html" not in content_type' in text
