from dataclasses import replace

from qrfacile_app.services.wine_rule_catalog import WineRuleCatalog, load_wine_rule_catalog
from qrfacile_app.services.wine_rule_validator import validate_wine_rule_catalog


def _catalog_with(**rule_changes) -> WineRuleCatalog:
    catalog = load_wine_rule_catalog()
    rules = dict(catalog.rules)
    for rule_id, changes in rule_changes.items():
        rules[rule_id] = replace(rules[rule_id], **changes)
    return WineRuleCatalog(
        version=catalog.version,
        score_weights=dict(catalog.score_weights),
        rules=rules,
    )


def test_current_catalog_is_enterprise_ready():
    report = validate_wine_rule_catalog(load_wine_rule_catalog())
    assert report.ready is True
    assert report.issues == ()
    assert report.rule_count >= 8
    assert report.active_rule_count == report.rule_count


def test_unknown_dependency_is_rejected():
    catalog = _catalog_with(**{
        "QRF-PACK-001": {"dependencies": ("QRF-NOT-FOUND",)},
    })
    report = validate_wine_rule_catalog(catalog)
    assert report.ready is False
    assert any(issue.code == "unknown_dependency" for issue in report.issues)


def test_self_dependency_is_rejected():
    catalog = _catalog_with(**{
        "QRF-CORE-001": {"dependencies": ("QRF-CORE-001",)},
    })
    report = validate_wine_rule_catalog(catalog)
    assert any(issue.code == "self_dependency" for issue in report.issues)


def test_dependency_cycle_is_rejected():
    catalog = _catalog_with(**{
        "QRF-CORE-001": {"dependencies": ("QRF-ELABEL-ING-001",)},
        "QRF-ELABEL-ING-001": {"dependencies": ("QRF-CORE-001",)},
    })
    report = validate_wine_rule_catalog(catalog)
    assert any(issue.code == "dependency_cycle" for issue in report.issues)


def test_duplicate_dependency_is_rejected():
    catalog = _catalog_with(**{
        "QRF-ELABEL-ALL-001": {
            "dependencies": ("QRF-ELABEL-ING-001", "QRF-ELABEL-ING-001"),
        },
    })
    report = validate_wine_rule_catalog(catalog)
    assert any(issue.code == "duplicate_dependency" for issue in report.issues)


def test_invalid_score_weight_order_is_rejected():
    catalog = load_wine_rule_catalog()
    invalid = WineRuleCatalog(
        version=catalog.version,
        score_weights={"PASS": 0, "WARNING": 100, "ERROR": 35},
        rules=dict(catalog.rules),
    )
    report = validate_wine_rule_catalog(invalid)
    assert any(issue.code == "weight_order" for issue in report.issues)


def test_error_rule_requires_documented_basis_outside_core():
    catalog = _catalog_with(**{
        "QRF-ELABEL-NUT-002": {"legal_basis": ()},
    })
    report = validate_wine_rule_catalog(catalog)
    assert any(
        issue.code == "missing_legal_basis" and issue.rule_id == "QRF-ELABEL-NUT-002"
        for issue in report.issues
    )
