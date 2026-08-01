from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.services.recycling_catalog import is_recycling_item_filled, validate_recycling_items
from qrfacile_app.services.recycling_persistence import RecyclingPersistenceError, persist_recycling_component
from qrfacile_app.wine_compliance_ui import _upsert_meta, _upsert_nutrition, _wine

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

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            wine = _wine(cur, int(wine_id))
    require_any_role(
        request,
        ("winery", "studio", "admin"),
        winery_id=int(wine["winery_id"]),
        need="edit",
    )

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

    try:
        energy_kj = int(_text(form, "energy_kj").strip())
        energy_kcal = int(_text(form, "energy_kcal").strip())
    except ValueError:
        return _redirect_error(wine_id, "Energia kJ e kcal obbligatoria e numerica")

    try:
        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                _upsert_nutrition(
                    cur, int(wine_id), energy_kj, energy_kcal,
                    *(_text(form, field) for field in ("fat", "saturates", "carbs", "sugars", "protein", "salt")),
                )
                _upsert_meta(
                    cur,
                    int(wine_id),
                    _text(form, "extra_ingredients").strip(),
                    _text(form, "story_text").strip(),
                    _text(form, "public_theme", "minimal").strip() or "minimal",
                )
                for component in COMPONENTS:
                    persist_recycling_component(cur, int(wine_id), component, {
                        "product": _text(form, f"rec_{component}_product"),
                        "code": _text(form, f"rec_{component}_code"),
                        "extra_code": _text(form, f"rec_{component}_extra"),
                        "note": _text(form, f"rec_{component}_note"),
                    })
            conn.commit()
    except RecyclingPersistenceError as exc:
        return _redirect_error(wine_id, str(exc))

    custom = validation["custom_codes"]
    if custom:
        codes = ", ".join(item["code"] for item in custom)
        return _redirect_error(wine_id, f"Codice personalizzato salvato: {codes}; verificare con il fornitore")
    return _redirect_error(wine_id, "Dati salvati correttamente")
