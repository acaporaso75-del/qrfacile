"""Estimate the nutrition declaration of a wine from data the winery has.

Most small wineries know the alcohol content and the residual sugar from the
oenologist's analysis, but not the energy value per 100 ml. This estimate
uses the conversion factors of Regulation (EU) No 1169/2011, Annex XIV:

    alcohol (ethanol)   29 kJ/g  7 kcal/g
    carbohydrate        17 kJ/g  4 kcal/g
    polyols (glycerol)  10 kJ/g  2.4 kcal/g
    organic acids       13 kJ/g  3 kcal/g

Ethanol in g per 100 ml = alcohol % vol x 0.789 (ethanol density, g/ml).
Fat, saturates, protein and salt are negligible in wine and set to 0.

The result is a proposal: the winery confirms or replaces it with laboratory
values, and remains responsible for the declaration.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

ETHANOL_DENSITY = Decimal("0.789")
FACTORS = {
    "alcohol": (Decimal("29"), Decimal("7")),
    "carbohydrate": (Decimal("17"), Decimal("4")),
    "polyol": (Decimal("10"), Decimal("2.4")),
    "organic_acid": (Decimal("13"), Decimal("3")),
}
FORMULA_TEXT = (
    "Stima con i fattori del Reg. (UE) 1169/2011, allegato XIV: alcol 29 kJ / 7 kcal per grammo "
    "(grammi = % vol × 0,789), zuccheri 17 kJ / 4 kcal, glicerolo 10 kJ / 2,4 kcal, acidi organici "
    "13 kJ / 3 kcal per grammo. Grassi, proteine e sale sono trascurabili nel vino e indicati come 0."
)


def _decimal(value: object, *, low: Decimal, high: Decimal, name: str) -> Decimal:
    try:
        number = Decimal(str(value).replace(",", ".")) if str(value or "").strip() else Decimal("0")
    except Exception as exc:  # noqa: BLE001 - any parse error is a user input error
        raise ValueError(f"{name} non è un numero") from exc
    if number < low or number > high:
        raise ValueError(f"{name} fuori dall'intervallo {low}-{high}")
    return number


def _round(value: Decimal, places: str) -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def estimate_wine_nutrition(
    alcohol_percent: object,
    residual_sugar_g_l: object,
    glycerol_g_l: object = 0,
    organic_acids_g_l: object = 0,
) -> dict[str, Decimal]:
    """Return per-100 ml values ready for the nutrition form."""
    alcohol = _decimal(alcohol_percent, low=Decimal("0"), high=Decimal("25"), name="Gradazione alcolica")
    sugar = _decimal(residual_sugar_g_l, low=Decimal("0"), high=Decimal("400"), name="Zuccheri residui")
    glycerol = _decimal(glycerol_g_l, low=Decimal("0"), high=Decimal("30"), name="Glicerolo")
    acids = _decimal(organic_acids_g_l, low=Decimal("0"), high=Decimal("20"), name="Acidità totale")

    grams = {
        "alcohol": alcohol * ETHANOL_DENSITY,
        "carbohydrate": sugar / 10,
        "polyol": glycerol / 10,
        "organic_acid": acids / 10,
    }
    kj = sum(grams[key] * FACTORS[key][0] for key in grams)
    kcal = sum(grams[key] * FACTORS[key][1] for key in grams)
    # Polyols are part of carbohydrates in the nutrition declaration.
    carbs = grams["carbohydrate"] + grams["polyol"]
    return {
        "energy_kj": _round(kj, "1"),
        "energy_kcal": _round(kcal, "1"),
        "fat": Decimal("0"),
        "saturates": Decimal("0"),
        "carbs": _round(carbs, "0.1"),
        "sugars": _round(grams["carbohydrate"], "0.1"),
        "protein": Decimal("0"),
        "salt": Decimal("0"),
    }


def estimator_js_constants() -> str:
    """The same factors for the in-page calculator, so both never diverge."""
    parts = [f"density:{ETHANOL_DENSITY}"]
    for key, (kj, kcal) in FACTORS.items():
        parts.append(f"{key}:[{kj},{kcal}]")
    return "{" + ",".join(parts) + "}"
