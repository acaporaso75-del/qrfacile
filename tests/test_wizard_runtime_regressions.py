from pathlib import Path

import pytest

from qrfacile_app.services.nutrition_validation import validate_nutrition_form
from qrfacile_app.services.recycling_catalog import resolve_recycling_selection


def test_recycling_material_change_replaces_stale_incompatible_code():
    glass = resolve_recycling_selection("bottle", "Vetro verde", "PET 1")
    cork = resolve_recycling_selection("closure", "Sughero", "PP 5")
    assert glass["suggested_code"] == "GL 71"
    assert glass["code_is_consistent"] is False
    assert cork["suggested_code"] == "FOR 51"
    assert cork["code_is_consistent"] is False


@pytest.mark.parametrize("field", ("fat", "saturates", "carbs", "sugars", "protein", "salt"))
def test_negative_nutrition_values_are_blocking(field):
    values = {"energy_kj": "350", "energy_kcal": "84", "fat": "0", "saturates": "0", "carbs": "2", "sugars": "1", "protein": "0", "salt": "0"}
    values[field] = "-1"
    result = validate_nutrition_form(values)
    assert result.errors
    assert field in result.errors[0].field


def test_nutrition_accepts_italian_decimals_and_rejects_text_and_impossible_values():
    valid = validate_nutrition_form({"energy_kj": "350", "energy_kcal": "84", "fat": "0,2", "saturates": "0,1", "carbs": "2,5", "sugars": "1,2", "protein": "0,3", "salt": "0,01"})
    assert not valid.errors
    assert valid.values["fat"] == "0.2"
    invalid = validate_nutrition_form({"energy_kj": "testo", "energy_kcal": "9999", "fat": "101"})
    assert len(invalid.errors) >= 3


def test_gross_kj_kcal_mismatch_is_blocking_and_small_difference_warns():
    gross = validate_nutrition_form({"energy_kj": "400", "energy_kcal": "400"})
    assert any(item.code == "energy_mismatch" for item in gross.errors)
    plausible = validate_nutrition_form({"energy_kj": "400", "energy_kcal": "90"})
    assert not plausible.errors
    assert any(item.code == "energy_check" for item in plausible.warnings)


def test_runtime_uses_one_upload_root_and_cache_busted_urls():
    source = Path("qrfacile_app/wine_images_ui.py").read_text(encoding="utf-8")
    storage = Path("qrfacile_app/services/storage.py").read_text(encoding="utf-8")
    assert "get_uploads_dir" in source
    assert "?v=" in storage
    assert "verify_saved_asset" in source


def test_final_review_and_completion_routes_exist():
    source = Path("qrfacile_app/wine_flow_ui.py").read_text(encoding="utf-8")
    assert '"/app/wine/{wine_id}/review"' in source
    assert '"/app/wine/{wine_id}/complete"' in source
    for text in ("Pubblica etichetta", "Apri pagina pubblica", "Apri anteprima", "Visualizza QR", "Scarica QR", "Esporta PDF", "Torna alla dashboard"):
        assert text in source
