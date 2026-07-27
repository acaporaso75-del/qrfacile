from qrfacile_app.wine_compliance_center_ui import _compact_compliance_html


def _report(*, publishable: bool, score: int, errors: int, warnings: int):
    results = []
    if errors:
        results.append({
            "status": "ERROR",
            "title": "Ingredienti obbligatori",
            "rule_id": "QRF-ELABEL-ING-001",
            "explanation": "La lista ingredienti non è presente.",
        })
    if warnings:
        results.append({
            "status": "WARNING",
            "title": "Imballaggi",
            "rule_id": "QRF-PACK-001",
            "explanation": "Completare il codice materiale.",
        })
    return {
        "publishable": publishable,
        "score": score,
        "counts": {"PASS": 7, "WARNING": warnings, "ERROR": errors},
        "results": results,
    }


def test_compact_center_shows_publishable_state_and_score():
    html = _compact_compliance_html(
        _report(publishable=True, score=96, errors=0, warnings=0),
        wine_id=12,
    )
    assert "Compliance Center" in html
    assert "Pubblicazione consentita" in html
    assert "96<small>/100</small>" in html
    assert "/app/wine/12/compliance-report" in html
    assert "aria-valuenow='96'" in html


def test_compact_center_shows_blocking_errors_and_explanations():
    html = _compact_compliance_html(
        _report(publishable=False, score=58, errors=1, warnings=1),
        wine_id=7,
    )
    assert "wineComplianceCenter blocked" in html
    assert "Pubblicazione bloccata" in html
    assert "1 errori · 1 avvisi" in html
    assert "Ingredienti obbligatori" in html
    assert "La lista ingredienti non è presente." in html


def test_compact_center_escapes_rule_content():
    report = _report(publishable=False, score=20, errors=1, warnings=0)
    report["results"][0]["title"] = "<script>alert(1)</script>"
    html = _compact_compliance_html(report, wine_id=1)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
