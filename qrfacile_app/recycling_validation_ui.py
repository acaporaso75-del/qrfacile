from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from qrfacile_app.services.recycling_catalog import is_recycling_item_filled, validate_recycling_items
from qrfacile_app.wine_compliance_ui import compliance_save as legacy_compliance_save

router = APIRouter(tags=["recycling-validation"])

COMPONENTS = ("bottle", "closure", "capsule", "label", "box", "other")
BASE_FIELDS = (
    "energy_kj",
    "energy_kcal",
    "fat",
    "saturates",
    "carbs",
    "sugars",
    "protein",
    "salt",
    "extra_ingredients",
    "story_text",
    "public_theme",
)


def _redirect_error(wine_id: int, message: str) -> RedirectResponse:
    return RedirectResponse(
        f"/app/wine/{int(wine_id)}/compliance?msg={quote(message)}",
        status_code=303,
    )


def _text(form, name: str, default: str = "") -> str:
    value = form.get(name, default)
    return str(value or "")


@router.post("/app/wine/{wine_id}/compliance/save")
async def validated_compliance_save(request: Request, wine_id: int):
    form = await request.form()

    recycle: dict[str, dict[str, str]] = {}
    for component in COMPONENTS:
        product = _text(form, f"rec_{component}_product").strip()
        code = _text(form, f"rec_{component}_code").strip()
        extra = _text(form, f"rec_{component}_extra").strip()
        note = _text(form, f"rec_{component}_note").strip()

        item = {
            "product": product,
            "code": code,
            "extra_code": extra,
            "note": note,
        }
        if is_recycling_item_filled(item):
            recycle[component] = item

    validation = validate_recycling_items(recycle)
    if validation["missing_codes"]:
        components = ", ".join(validation["missing_codes"])
        return _redirect_error(
            wine_id,
            f"Codice ambientale mancante per: {components}",
        )

    if validation["mismatches"]:
        components = sorted({item.get("component", "") for item in validation["mismatches"]})
        labels = ", ".join(component for component in components if component)
        return _redirect_error(
            wine_id,
            f"Materiale e codice riciclabilità non coerenti per: {labels}",
        )

    kwargs = {field: _text(form, field) for field in BASE_FIELDS}
    for component in COMPONENTS:
        kwargs[f"rec_{component}_product"] = _text(form, f"rec_{component}_product")
        kwargs[f"rec_{component}_code"] = _text(form, f"rec_{component}_code")
        kwargs[f"rec_{component}_extra"] = _text(form, f"rec_{component}_extra")
        kwargs[f"rec_{component}_note"] = _text(form, f"rec_{component}_note")

    return legacy_compliance_save(request=request, wine_id=wine_id, **kwargs)
