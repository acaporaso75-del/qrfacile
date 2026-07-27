from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping

from qrfacile_app.services.wine_rule_catalog import load_wine_rule_catalog

ENGINE_VERSION = "2026.07.2"

PASS = "PASS"
WARNING = "WARNING"
ERROR = "ERROR"


@dataclass(frozen=True)
class ComplianceResult:
    rule_id: str
    version: str
    status: str
    title: str
    explanation: str
    field: str | None = None
    remediation: str | None = None
    evidence: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _result(
    rule_id: str,
    status: str,
    title: str,
    explanation: str,
    *,
    field: str | None = None,
    remediation: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> ComplianceResult:
    return ComplianceResult(
        rule_id=rule_id,
        version=ENGINE_VERSION,
        status=status,
        title=title,
        explanation=explanation,
        field=field,
        remediation=remediation,
        evidence=evidence or {},
    )


def _check_identity(payload: Mapping[str, Any]) -> list[ComplianceResult]:
    wine = payload.get("wine") or {}
    name = _text(wine.get("wine_name"))
    if name:
        return [_result(
            "QRF-CORE-001",
            PASS,
            "Identità del vino presente",
            "La denominazione del vino è valorizzata.",
            field="wine.wine_name",
            evidence={"wine_name": name},
        )]
    return [_result(
        "QRF-CORE-001",
        ERROR,
        "Denominazione del vino mancante",
        "Il prodotto non può essere identificato in modo univoco senza una denominazione.",
        field="wine.wine_name",
        remediation="Inserire la denominazione del vino prima della pubblicazione.",
    )]


def _check_ingredients(payload: Mapping[str, Any]) -> list[ComplianceResult]:
    ingredients = [str(x).strip() for x in (payload.get("ingredients") or []) if str(x).strip()]
    extra = _text((payload.get("meta") or {}).get("extra_ingredients"))
    if ingredients or extra:
        return [_result(
            "QRF-ELABEL-ING-001",
            PASS,
            "Ingredienti presenti",
            "È presente almeno una voce nella dichiarazione degli ingredienti.",
            field="ingredients",
            evidence={"master_count": len(ingredients), "extra_present": bool(extra)},
        )]
    return [_result(
        "QRF-ELABEL-ING-001",
        ERROR,
        "Ingredienti mancanti",
        "La dichiarazione degli ingredienti non contiene alcuna voce.",
        field="ingredients",
        remediation="Inserire gli ingredienti applicabili e sottoporli a revisione umana.",
    )]


def _check_allergens(payload: Mapping[str, Any]) -> list[ComplianceResult]:
    allergens = [str(x).strip() for x in (payload.get("allergens") or []) if str(x).strip()]
    if allergens:
        return [_result(
            "QRF-ELABEL-ALL-001",
            PASS,
            "Allergeni dichiarati",
            "È presente almeno una dichiarazione relativa agli allergeni.",
            field="allergens",
            evidence={"count": len(allergens)},
        )]
    return [_result(
        "QRF-ELABEL-ALL-001",
        WARNING,
        "Allergeni non dichiarati",
        "Non risultano allergeni selezionati. Il sistema non può stabilire automaticamente se l'assenza sia corretta.",
        field="allergens",
        remediation="Verificare la scheda tecnica e confermare esplicitamente la presenza o l'assenza di allergeni.",
    )]


def _check_energy(payload: Mapping[str, Any]) -> list[ComplianceResult]:
    nutrition = payload.get("nutrition") or {}
    kj = _decimal(nutrition.get("energy_kj"))
    kcal = _decimal(nutrition.get("energy_kcal"))
    results: list[ComplianceResult] = []

    if kj is None or kcal is None:
        return [_result(
            "QRF-ELABEL-NUT-001",
            ERROR,
            "Valore energetico incompleto",
            "Devono essere valorizzati sia kJ sia kcal.",
            field="nutrition.energy",
            remediation="Inserire entrambi i valori energetici e verificare l'unità di riferimento.",
            evidence={"energy_kj": nutrition.get("energy_kj"), "energy_kcal": nutrition.get("energy_kcal")},
        )]

    if kj < 0 or kcal < 0:
        results.append(_result(
            "QRF-ELABEL-NUT-002",
            ERROR,
            "Valore energetico negativo",
            "I valori energetici non possono essere negativi.",
            field="nutrition.energy",
            remediation="Correggere i valori energetici.",
            evidence={"energy_kj": str(kj), "energy_kcal": str(kcal)},
        ))
    else:
        results.append(_result(
            "QRF-ELABEL-NUT-001",
            PASS,
            "Valore energetico presente",
            "Sono presenti i valori energetici in kJ e kcal.",
            field="nutrition.energy",
            evidence={"energy_kj": str(kj), "energy_kcal": str(kcal)},
        ))

    expected_kcal = kj / Decimal("4.184") if kj >= 0 else Decimal("0")
    tolerance = max(Decimal("2"), expected_kcal * Decimal("0.08"))
    if abs(kcal - expected_kcal) > tolerance:
        results.append(_result(
            "QRF-ELABEL-NUT-003",
            WARNING,
            "Possibile incoerenza tra kJ e kcal",
            "La conversione tecnica tra i due valori supera la tolleranza configurata dal motore.",
            field="nutrition.energy",
            remediation="Verificare i valori sulla documentazione analitica; il controllo è indicativo e richiede revisione umana.",
            evidence={
                "energy_kj": str(kj),
                "energy_kcal": str(kcal),
                "expected_kcal_technical": str(expected_kcal.quantize(Decimal("0.1"))),
                "tolerance": str(tolerance.quantize(Decimal("0.1"))),
            },
        ))
    else:
        results.append(_result(
            "QRF-ELABEL-NUT-003",
            PASS,
            "Coerenza tecnica kJ/kcal",
            "I valori rientrano nella tolleranza tecnica configurata.",
            field="nutrition.energy",
        ))
    return results


def _check_nutrition_values(payload: Mapping[str, Any]) -> list[ComplianceResult]:
    nutrition = payload.get("nutrition") or {}
    fields = ("fat", "saturates", "carbs", "sugars", "protein", "salt")
    invalid: list[str] = []
    missing: list[str] = []
    for field in fields:
        raw = nutrition.get(field)
        value = _decimal(raw)
        if value is None:
            missing.append(field)
        elif value < 0:
            invalid.append(field)

    if invalid:
        return [_result(
            "QRF-ELABEL-NUT-004",
            ERROR,
            "Valori nutrizionali negativi",
            "Uno o più valori nutrizionali risultano negativi.",
            field="nutrition",
            remediation="Correggere i campi indicati.",
            evidence={"invalid_fields": invalid},
        )]
    if missing:
        return [_result(
            "QRF-ELABEL-NUT-004",
            WARNING,
            "Valori nutrizionali da verificare",
            "Uno o più campi nutrizionali non risultano valorizzati.",
            field="nutrition",
            remediation="Verificare se i valori mancanti debbano essere dichiarati o rappresentati come zero.",
            evidence={"missing_fields": missing},
        )]
    return [_result(
        "QRF-ELABEL-NUT-004",
        PASS,
        "Valori nutrizionali valorizzati",
        "I principali campi nutrizionali sono presenti e non negativi.",
        field="nutrition",
    )]


def _check_recycling(payload: Mapping[str, Any]) -> list[ComplianceResult]:
    recycle = payload.get("recycle") or {}
    if not recycle:
        return [_result(
            "QRF-PACK-001",
            WARNING,
            "Informazioni ambientali assenti",
            "Non risultano componenti di imballaggio registrati.",
            field="recycle",
            remediation="Inserire i componenti applicabili e verificarne materiale e codice.",
        )]

    incomplete = []
    for component, item in recycle.items():
        if not _text((item or {}).get("code")) or _text((item or {}).get("code")) == "-":
            incomplete.append(component)
    if incomplete:
        return [_result(
            "QRF-PACK-001",
            WARNING,
            "Codici ambientali incompleti",
            "Alcuni componenti non hanno un codice materiale valorizzato.",
            field="recycle",
            remediation="Completare i codici dopo verifica con il fornitore dell'imballaggio.",
            evidence={"components": incomplete},
        )]
    return [_result(
        "QRF-PACK-001",
        PASS,
        "Informazioni ambientali presenti",
        "I componenti registrati dispongono di un codice materiale.",
        field="recycle",
        evidence={"component_count": len(recycle)},
    )]


def _enrich_result(result: ComplianceResult, catalog) -> dict[str, Any] | None:
    rule = catalog.get(result.rule_id)
    if not rule.active:
        return None

    item = result.to_dict()
    item.update({
        "catalog_version": catalog.version,
        "domain": rule.domain,
        "blocking": rule.blocking,
        "legal_basis": list(rule.legal_basis),
        "human_review_required": rule.human_review_required,
        "default_severity": rule.default_severity,
    })
    return item


def run_wine_compliance(payload: Mapping[str, Any]) -> dict[str, Any]:
    catalog = load_wine_rule_catalog()
    checks: Iterable[list[ComplianceResult]] = (
        _check_identity(payload),
        _check_ingredients(payload),
        _check_allergens(payload),
        _check_energy(payload),
        _check_nutrition_values(payload),
        _check_recycling(payload),
    )

    enriched_results: list[dict[str, Any]] = []
    for result in (result for group in checks for result in group):
        enriched = _enrich_result(result, catalog)
        if enriched is not None:
            enriched_results.append(enriched)

    counts = {PASS: 0, WARNING: 0, ERROR: 0}
    for item in enriched_results:
        counts[item["status"]] += 1

    penalty = sum(int(catalog.score_weights.get(item["status"], 0)) for item in enriched_results)
    score = 100 if not enriched_results else max(0, round(100 - (penalty / len(enriched_results))))
    blocking_errors = [
        item for item in enriched_results
        if item["status"] == ERROR and bool(item.get("blocking"))
    ]

    return {
        "engine_version": ENGINE_VERSION,
        "catalog_version": catalog.version,
        "score": score,
        "publishable": not blocking_errors,
        "blocking_error_count": len(blocking_errors),
        "requires_human_review": any(bool(item.get("human_review_required")) for item in enriched_results),
        "counts": counts,
        "results": enriched_results,
    }
