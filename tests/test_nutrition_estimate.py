"""Nutrition calculator from alcohol and residual sugar (EU 1169/2011 Annex XIV)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from qrfacile_app.services.nutrition_estimate import (
    FACTORS,
    estimate_wine_nutrition,
    estimator_js_constants,
)
from qrfacile_app.services.nutrition_validation import validate_nutrition_form


def test_dry_red_wine_estimate():
    values = estimate_wine_nutrition("13,5", "2")
    # ethanol 13.5 x 0.789 = 10.65 g -> 308.9 kJ / 74.6 kcal; sugar 0.2 g -> 3.4 kJ / 0.8 kcal
    assert values["energy_kj"] == Decimal("312")
    assert values["energy_kcal"] == Decimal("75")
    assert (values["carbs"], values["sugars"]) == (Decimal("0.2"), Decimal("0.2"))
    assert values["fat"] == values["saturates"] == values["protein"] == values["salt"] == Decimal("0")


def test_glycerol_counts_as_carbohydrate_and_acids_add_energy():
    values = estimate_wine_nutrition(13.5, 2, glycerol_g_l=7, organic_acids_g_l="5,5")
    assert (values["energy_kj"], values["energy_kcal"]) == (Decimal("326"), Decimal("79"))
    assert values["carbs"] == Decimal("0.9") and values["sugars"] == Decimal("0.2")


def test_sweet_wine_estimate():
    values = estimate_wine_nutrition(11, 120)
    assert values["sugars"] == Decimal("12.0") and values["carbs"] == Decimal("12.0")
    assert values["energy_kcal"] == Decimal("109")


@pytest.mark.parametrize(
    "alcohol, sugar",
    [(13.5, 2), (12, 0), (11, 120), (15, 45), (5.5, 60), (0, 30)],
)
def test_estimates_pass_the_existing_nutrition_validation(alcohol, sugar):
    values = estimate_wine_nutrition(alcohol, sugar)
    result = validate_nutrition_form({key: str(value) for key, value in values.items()})
    assert result.errors == ()
    assert result.warnings == ()


@pytest.mark.parametrize("alcohol, sugar", [("abc", 2), (30, 2), (13, -1), (13, 500)])
def test_invalid_inputs_are_refused(alcohol, sugar):
    with pytest.raises(ValueError):
        estimate_wine_nutrition(alcohol, sugar)


def test_page_calculator_uses_the_same_factors():
    constants = estimator_js_constants()
    assert "density:0.789" in constants
    for key, (kj, kcal) in FACTORS.items():
        assert f"{key}:[{kj},{kcal}]" in constants

    from qrfacile_app.wine_compliance_ui import _nutrition_estimator_html

    html = _nutrition_estimator_html()
    assert "__CONSTANTS__" not in html and "__FORMULA__" not in html
    assert constants in html
    assert "Usa questi valori" in html and "1169/2011" in html
    assert "ricordati di salvare" in html
