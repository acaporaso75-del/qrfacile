from __future__ import annotations

from typing import Any, Mapping

CATALOG_VERSION = "2026.07.4"
CATALOG_SOURCE = "Decisione 97/129/CE"

RECYCLING_CATALOG: list[dict[str, Any]] = [
    {"family": "Plastica", "material": "PET - Polietilene tereftalato", "code": "PET 1", "collection": "Raccolta plastica", "components": ["bottle", "closure", "capsule", "label", "other"]},
    {"family": "Plastica", "material": "HDPE - Polietilene ad alta densità", "code": "HDPE 2", "collection": "Raccolta plastica", "components": ["closure", "capsule", "other"]},
    {"family": "Plastica", "material": "PVC - Polivinilcloruro", "code": "PVC 3", "collection": "Verificare le disposizioni comunali", "components": ["capsule", "label", "other"]},
    {"family": "Plastica", "material": "LDPE - Polietilene a bassa densità", "code": "LDPE 4", "collection": "Raccolta plastica", "components": ["capsule", "label", "other"]},
    {"family": "Plastica", "material": "PP - Polipropilene", "code": "PP 5", "collection": "Raccolta plastica", "components": ["closure", "capsule", "label", "other"]},
    {"family": "Plastica", "material": "PS - Polistirene", "code": "PS 6", "collection": "Raccolta plastica", "components": ["closure", "other"]},
    {"family": "Plastica", "material": "Altre plastiche", "code": "OTHER 7", "collection": "Verificare le disposizioni comunali", "components": ["closure", "capsule", "label", "other"]},
    {"family": "Carta e cartone", "material": "Cartone ondulato", "code": "PAP 20", "collection": "Raccolta carta", "components": ["box", "other"]},
    {"family": "Carta e cartone", "material": "Cartone non ondulato", "code": "PAP 21", "collection": "Raccolta carta", "components": ["box", "other"]},
    {"family": "Carta e cartone", "material": "Carta", "code": "PAP 22", "collection": "Raccolta carta", "components": ["label", "box", "other"]},
    {"family": "Metalli", "material": "Acciaio / banda stagnata", "code": "FE 40", "collection": "Raccolta metalli", "components": ["closure", "capsule", "other"]},
    {"family": "Metalli", "material": "Alluminio", "code": "ALU 41", "collection": "Raccolta metalli", "components": ["closure", "capsule", "other"]},
    {"family": "Legno", "material": "Legno", "code": "FOR 50", "collection": "Raccolta legno", "components": ["box", "other"]},
    {"family": "Legno", "material": "Sughero", "code": "FOR 51", "collection": "Raccolta dedicata; verificare il Comune", "components": ["closure", "other"]},
    {"family": "Tessili", "material": "Cotone", "code": "COT 60", "collection": "Raccolta tessili", "components": ["other"]},
    {"family": "Tessili", "material": "Iuta", "code": "TEX 61", "collection": "Raccolta tessili", "components": ["other"]},
    {"family": "Vetro", "material": "Vetro incolore", "code": "GL 70", "collection": "Raccolta vetro", "components": ["bottle", "other"]},
    {"family": "Vetro", "material": "Vetro verde", "code": "GL 71", "collection": "Raccolta vetro", "components": ["bottle", "other"]},
    {"family": "Vetro", "material": "Vetro marrone", "code": "GL 72", "collection": "Raccolta vetro", "components": ["bottle", "other"]},
    {"family": "Composti", "material": "Carta/cartone + metalli diversi", "code": "C/PAP 80", "collection": "Verificare materiale prevalente e disposizioni comunali", "components": ["box", "other"]},
    {"family": "Composti", "material": "Carta/cartone + plastica", "code": "C/PAP 81", "collection": "Verificare materiale prevalente e disposizioni comunali", "components": ["label", "box", "other"]},
    {"family": "Composti", "material": "Carta/cartone + alluminio", "code": "C/PAP 82", "collection": "Verificare materiale prevalente e disposizioni comunali", "components": ["label", "box", "other"]},
    {"family": "Composti", "material": "Carta/cartone + banda stagnata", "code": "C/PAP 83", "collection": "Verificare materiale prevalente e disposizioni comunali", "components": ["box", "other"]},
    {"family": "Composti", "material": "Carta/cartone + plastica + alluminio", "code": "C/PAP 84", "collection": "Verificare materiale prevalente e disposizioni comunali", "components": ["label", "box", "other"]},
    {"family": "Composti", "material": "Carta/cartone + plastica + alluminio + banda stagnata", "code": "C/PAP 85", "collection": "Verificare materiale prevalente e disposizioni comunali", "components": ["box", "other"]},
    {"family": "Composti", "material": "Plastica + alluminio", "code": "C/OTHER 90", "collection": "Verificare polimero prevalente e disposizioni comunali", "components": ["closure", "capsule", "label", "other"]},
    {"family": "Composti", "material": "Plastica + banda stagnata", "code": "C/OTHER 91", "collection": "Verificare polimero prevalente e disposizioni comunali", "components": ["closure", "capsule", "other"]},
    {"family": "Composti", "material": "Plastica + metalli diversi", "code": "C/OTHER 92", "collection": "Verificare polimero prevalente e disposizioni comunali", "components": ["closure", "capsule", "other"]},
    {"family": "Composti", "material": "Vetro + plastica", "code": "C/GL 95", "collection": "Verificare materiale prevalente e disposizioni comunali", "components": ["bottle", "other"]},
    {"family": "Composti", "material": "Vetro + alluminio", "code": "C/GL 96", "collection": "Verificare materiale prevalente e disposizioni comunali", "components": ["bottle", "other"]},
    {"family": "Composti", "material": "Vetro + banda stagnata", "code": "C/GL 97", "collection": "Verificare materiale prevalente e disposizioni comunali", "components": ["bottle", "other"]},
    {"family": "Composti", "material": "Vetro + metalli diversi", "code": "C/GL 98", "collection": "Verificare materiale prevalente e disposizioni comunali", "components": ["bottle", "other"]},
    {"family": "Biobased / innovativi", "material": "Polimero biobased o compostabile", "code": "", "collection": "Usare solo il codice comunicato dal fornitore; verificare certificazioni e Comune", "components": ["closure", "capsule", "label", "other"], "custom": True},
    {"family": "Personalizzato", "material": "Altro materiale / codice personalizzato", "code": "", "collection": "Verificare con il fornitore dell'imballaggio e con il Comune", "components": ["bottle", "closure", "capsule", "label", "box", "other"], "custom": True},
]


RECYCLING_COMPONENT_PRIORITIES: dict[str, tuple[str, ...]] = {
    "bottle": ("GL 71", "GL 72", "GL 70", "PET 1", "C/GL 95", "C/GL 96", "C/GL 97", "C/GL 98"),
    "closure": ("FOR 51", "PP 5", "ALU 41", "FE 40", "HDPE 2", "PS 6", "OTHER 7"),
    "capsule": ("ALU 41", "PVC 3", "PET 1", "PP 5", "LDPE 4", "FE 40"),
    "label": ("PAP 22", "PP 5", "PET 1", "PVC 3", "LDPE 4"),
    "box": ("PAP 20", "PAP 21", "PAP 22", "FOR 50"),
    "other": (),
}


def normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def get_recycling_suggestions(component: Any) -> list[dict[str, Any]]:
    """Return every compatible catalog item in component-specific priority order."""
    component_key = normalize(component)
    compatible = [
        item for item in RECYCLING_CATALOG
        if component_key in {normalize(value) for value in item.get("components") or []}
    ]
    priorities = {
        normalize(code): position
        for position, code in enumerate(RECYCLING_COMPONENT_PRIORITIES.get(component_key, ()))
    }
    fallback = len(priorities)
    catalog_positions = {id(item): position for position, item in enumerate(RECYCLING_CATALOG)}
    return sorted(
        compatible,
        key=lambda item: (
            priorities.get(normalize(item.get("code")), fallback),
            catalog_positions[id(item)],
        ),
    )


def is_recycling_item_filled(item: Mapping[str, Any] | None) -> bool:
    """Return whether a recycling row contains user-provided information.

    Old records are pre-populated with ``code='-'`` and empty values in all
    other fields.  That sentinel is storage compatibility data, not a real
    packaging component.
    """
    row = item or {}
    product = str(row.get("product") or "").strip()
    code = str(row.get("code") or "").strip()
    extra_code = str(row.get("extra_code") or "").strip()
    note = str(row.get("note") or "").strip()
    return bool(product or (code and code != "-") or extra_code or note)


def normalize_recycling_items(
    recycle: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Discard storage-only legacy placeholders while preserving real rows."""
    return {
        str(component): dict(raw or {})
        for component, raw in (recycle or {}).items()
        if is_recycling_item_filled(raw)
    }


_BY_CODE = {normalize(item["code"]): item for item in RECYCLING_CATALOG if item.get("code")}
_BY_MATERIAL = {normalize(item["material"]): item for item in RECYCLING_CATALOG}


def find_by_code(code: Any) -> dict[str, Any] | None:
    return _BY_CODE.get(normalize(code))


def find_by_material(material: Any) -> dict[str, Any] | None:
    return _BY_MATERIAL.get(normalize(material))


def validate_recycling_items(recycle: Mapping[str, Mapping[str, Any]] | None) -> dict[str, Any]:
    items = normalize_recycling_items(recycle)
    missing_codes: list[str] = []
    custom_codes: list[dict[str, str]] = []
    mismatches: list[dict[str, str]] = []
    known_codes: list[str] = []

    for component, raw in items.items():
        item = raw or {}
        code = str(item.get("code") or "").strip()
        material = str(item.get("product") or "").strip()
        if not code or code == "-":
            missing_codes.append(str(component))
            continue

        catalog_item = find_by_code(code)
        if catalog_item is None:
            custom_codes.append({"component": str(component), "code": code, "material": material})
            continue

        known_codes.append(code)
        allowed_components = set(catalog_item.get("components") or [])
        if allowed_components and str(component) not in allowed_components:
            mismatches.append({
                "component": str(component),
                "code": code,
                "expected_components": ", ".join(sorted(allowed_components)),
            })

        material_item = find_by_material(material) if material else None
        if material_item and normalize(material_item.get("code")) != normalize(code):
            mismatches.append({
                "component": str(component),
                "code": code,
                "material": material,
                "expected_code": str(material_item.get("code") or ""),
            })

    return {
        "catalog_version": CATALOG_VERSION,
        "source": CATALOG_SOURCE,
        "component_count": len(items),
        "known_codes": known_codes,
        "missing_codes": missing_codes,
        "custom_codes": custom_codes,
        "mismatches": mismatches,
        "all_known_and_consistent": bool(items) and not missing_codes and not custom_codes and not mismatches,
    }
