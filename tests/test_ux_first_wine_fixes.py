"""Regressions found in the 2026-11-21 usability review on staging."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from qrfacile_app import guided_flow, ui_shell
from qrfacile_app.public import _num
from qrfacile_app.services.recycling_catalog import canonical_recycling_code, validate_recycling_items
from qrfacile_app.services.recycling_persistence import normalize_recycling_value


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "typed, expected",
    [
        ("GL 71GL71", "GL 71"),   # pre-filled code + typed code, as seen on staging
        ("GL71", "GL 71"),
        ("gl 71", "GL 71"),
        ("FOR 51FOR51", "FOR 51"),
        ("PAP22", "PAP 22"),
        ("C/PAP81", "C/PAP 81"),
        ("XYZ 9", "XYZ 9"),       # unknown codes are kept, only trimmed
        ("", ""),
    ],
)
def test_recycling_codes_are_stored_in_catalog_spelling(typed, expected):
    assert canonical_recycling_code(typed) == expected


def test_saved_duplicate_code_becomes_a_known_consistent_code():
    stored = normalize_recycling_value({"product": "Vetro verde", "code": "GL 71GL71"})
    assert stored.code == "GL 71"
    report = validate_recycling_items({"bottle": {"product": "Vetro verde", "code": "GL 71GL71"}})
    assert report["custom_codes"] == [] and report["mismatches"] == []
    assert report["all_known_and_consistent"] is True


def test_public_page_repairs_already_stored_duplicates():
    source = (ROOT / "qrfacile_app" / "public.py").read_text(encoding="utf-8")
    assert 'code = canonical_recycling_code(r.get("code"))' in source
    editor = (ROOT / "qrfacile_app" / "wine_compliance_ui.py").read_text(encoding="utf-8")
    assert 'placeholder="es. GL 71"' in editor


@pytest.mark.parametrize(
    "value, locale, expected",
    [
        (Decimal("0.000"), "it", "0"),
        (Decimal("2.600"), "it", "2,6"),
        (Decimal("2.600"), "en", "2.6"),
        (Decimal("13.250"), "it", "13,25"),
        (328, "it", "328"),
        (None, "it", "—"),
    ],
)
def test_public_nutrition_values_are_readable(value, locale, expected):
    assert _num(value, locale) == expected


def test_steps_are_complete_only_when_their_data_is_saved():
    empty = guided_flow.completion_from_counts(
        wine_name="Aglianico", lot="L1", has_front_image=False, ingredients=0,
        allergens=0, has_energy=False, recycling=0, published=False,
    )
    assert empty == {"wine"}
    partial = guided_flow.completion_from_counts(
        wine_name="Aglianico", lot="L1", has_front_image=True, ingredients=1,
        allergens=0, has_energy=True, recycling=0, published=False,
    )
    assert partial == {"wine", "images", "nutrition"}
    ready = guided_flow.completion_from_counts(
        wine_name="Aglianico", lot="L1", has_front_image=True, ingredients=1,
        allergens=1, has_energy=True, recycling=2, published=True,
    )
    assert ready == {"wine", "images", "ingredients", "nutrition", "recycling", "review", "publish"}


def test_no_page_hardcodes_completed_steps():
    for name in ("wine_compliance_ui.py", "wine_images_ui.py", "wine_flow_ui.py"):
        source = (ROOT / "qrfacile_app" / name).read_text(encoding="utf-8")
        assert "completed_steps(int(wine_id))" in source, name
    hub = (ROOT / "qrfacile_app" / "wine_hub_ui.py").read_text(encoding="utf-8")
    assert '"completed": set(complete)' not in hub


def test_sidebar_loads_real_balance_instead_of_showing_zero(monkeypatch):
    monkeypatch.setattr(ui_shell, "_credits_for_email", lambda email: {"wine": 2, "generic": 0})
    html = ui_shell._sidebar("winery", "cantina@example.test", {})
    assert "QR vino" in html and "<b>2</b>" in html
    assert "<span>wine</span>" not in html and "<span>generic</span>" not in html

    monkeypatch.setattr(ui_shell, "_credits_for_email", lambda email: None)
    unknown = ui_shell._sidebar("winery", "cantina@example.test", None)
    assert "<b>—</b>" in unknown and "<b>0</b>" not in unknown
