from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Mapping


@dataclass(frozen=True)
class NutritionIssue:
    field: str
    code: str
    message: str


@dataclass(frozen=True)
class NutritionValidation:
    values: dict[str, str]
    errors: tuple[NutritionIssue, ...]
    warnings: tuple[NutritionIssue, ...]


FIELDS = ("energy_kj", "energy_kcal", "fat", "saturates", "carbs", "sugars", "protein", "salt")
MACROS = ("fat", "saturates", "carbs", "sugars", "protein", "salt")


def _number(raw: object) -> Decimal | None:
    text = str(raw or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise ValueError
    if not value.is_finite():
        raise ValueError
    return value


def _format(value: Decimal | None) -> str:
    if value is None:
        return "0"
    return format(value.normalize(), "f")


def validate_nutrition_form(raw: Mapping[str, object]) -> NutritionValidation:
    errors: list[NutritionIssue] = []
    warnings: list[NutritionIssue] = []
    parsed: dict[str, Decimal | None] = {}
    for field in FIELDS:
        try:
            parsed[field] = _number(raw.get(field))
        except ValueError:
            parsed[field] = None
            errors.append(NutritionIssue(field, "not_numeric", "Inserire un valore numerico usando virgola o punto per i decimali."))

    for field in ("energy_kj", "energy_kcal"):
        if parsed[field] is None and not any(issue.field == field for issue in errors):
            errors.append(NutritionIssue(field, "required", "Campo obbligatorio."))

    limits = {"energy_kj": Decimal("5000"), "energy_kcal": Decimal("1200"), **{field: Decimal("100") for field in MACROS}}
    for field, value in parsed.items():
        if value is None:
            continue
        if value < 0:
            errors.append(NutritionIssue(field, "negative", "Il valore non può essere negativo."))
        elif value > limits[field]:
            errors.append(NutritionIssue(field, "impossible", "Valore fuori dall’intervallo plausibile per 100 ml."))

    kj, kcal = parsed["energy_kj"], parsed["energy_kcal"]
    if kj is not None and kcal is not None and kj >= 0 and kcal >= 0:
        expected = kj / Decimal("4.184")
        difference = abs(kcal - expected)
        if difference > max(Decimal("12"), expected * Decimal("0.20")):
            errors.append(NutritionIssue("energy_kj,energy_kcal", "energy_mismatch", "kJ e kcal non sono coerenti: verificare le unità e i valori."))
        elif difference > max(Decimal("2"), expected * Decimal("0.05")):
            warnings.append(NutritionIssue("energy_kj,energy_kcal", "energy_check", "La conversione kJ/kcal è leggermente diversa: verificare la scheda tecnica."))

    for child, parent in (("saturates", "fat"), ("sugars", "carbs")):
        if parsed[child] is not None and parsed[parent] is not None and parsed[child] > parsed[parent]:
            errors.append(NutritionIssue(f"{child},{parent}", "subset", "Il valore specifico non può superare il totale."))

    return NutritionValidation(
        values={field: _format(parsed[field]) for field in FIELDS},
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
