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


def test_winery_lands_on_dashboard_after_login():
    source = (ROOT / "qrfacile_app" / "auth_routes.py").read_text(encoding="utf-8")
    assert 'next_url = "/app/dashboard" if (u.get("role") or "").lower().strip() == "winery" else "/app/start"' in source
    assert "Ti abbiamo inviato un’email" in source
    assert "Ora puoi accedere.\"" not in source.split("created == \"1\"")[1].split("elif")[0]


def _row(**flags):
    row = {"wine_id": 9, "wine_name": "Aglianico", "status": "bozza", "slug": "ABC"}
    row.update(flags)
    return row


def test_first_wine_checklist_guides_until_first_publication():
    from qrfacile_app.dashboard_ui import _first_wine_checklist

    empty = _first_wine_checklist([], 0, "winery")
    assert "Il tuo primo vino" in empty
    assert "Continua: Dai un nome al tuo vino" in empty and 'href="/app/new-wine-master"' in empty

    started = _first_wine_checklist([_row(ingredient_count=1, allergen_count=1)], 1, "winery")
    assert "Continua: Valori nutrizionali" in started
    assert 'href="/app/wine/9/compliance#nutrizione"' in started

    published = _first_wine_checklist([_row(status="attiva")], 1, "winery")
    assert published == ""
    assert _first_wine_checklist([], 0, "studio") == ""


def test_final_check_has_only_clear_actions():
    source = (ROOT / "qrfacile_app" / "wine_flow_ui.py").read_text(encoding="utf-8")
    assert "Torna a correggere" in source
    for removed in (">Indietro<", ">Modifica<", ">Salva dati<", "Compliance Score"):
        assert removed not in source
    assert '"closure": "Tappo"' in source


def test_export_leads_with_one_pdf_for_the_printer():
    source = (ROOT / "qrfacile_app" / "export_qr_ui.py").read_text(encoding="utf-8")
    assert "Scarica PDF per la tipografia" in source
    assert "export/file?preset=a4_pdf" in source
    simple = source.index("Scarica PDF per la tipografia")
    advanced = source.index('<details class="exportAdvanced">')
    assert simple < advanced < source.index("Preset tipografico")


def test_customer_pages_avoid_technical_jargon():
    checks = {
        "wine_images_ui.py": ("Anti-bomb",),
        "wine_compliance_ui.py": ("Richiedi sblocco admin",),
        "wine_hub_ui.py": ("<span>Slug ",),
        "dashboard_ui.py": ("Slug {slug_safe", 'pill(f"wine: {balances'),
        "start_ui.py": ('pill(f"generic: ',),
    }
    for name, forbidden in checks.items():
        source = (ROOT / "qrfacile_app" / name).read_text(encoding="utf-8")
        for text in forbidden:
            assert text not in source, (name, text)


def test_packaging_presets_use_valid_catalog_codes_for_each_component():
    from qrfacile_app.services.recycling_catalog import PACKAGING_PRESETS, find_by_code

    assert len(PACKAGING_PRESETS) >= 3
    for preset in PACKAGING_PRESETS:
        assert preset["label"] and preset["items"]
        report = validate_recycling_items({
            component: {"product": find_by_code(code)["material"], "code": code}
            for component, code in preset["items"].items()
        })
        assert report["all_known_and_consistent"], preset["key"]


def test_compliance_page_offers_presets_and_repairs_typed_duplicates():
    from qrfacile_app.recycling_guidance_ui import _guidance_markup

    html = _guidance_markup()
    assert "Scegli il tuo imballaggio" in html
    assert "Bottiglia verde + tappo in sughero" in html
    assert "const lookupCode" in html and "if (item && item.code) code.value = item.code;" in html


def test_dashboard_first_wine_mode_hides_overlapping_panels():
    source = (ROOT / "qrfacile_app" / "dashboard_ui.py").read_text(encoding="utf-8")
    assert 'first_wine_mode = bool(first_wine_html) and role == "winery" and view != "full"' in source
    assert 'full_dashboard_html = "" if first_wine_mode else f"""' in source
    assert "/app/dashboard?view=full" in source
    # hero, guided compliance panel and search live inside the full view only
    full = source.split('full_dashboard_html = "" if first_wine_mode else f"""', 1)[1].split('    """\n', 1)[0]
    for block in ('class="dashboardHero"', "{onboarding_html}", 'class="dashboardToolbar card"'):
        assert block in full


def test_new_lot_page_is_plain_and_studio_section_optional():
    source = (ROOT / "qrfacile_app" / "premium_ui.py").read_text(encoding="utf-8")
    assert "Lavori con uno studio grafico? (facoltativo)" in source
    assert '<details class="newWineStudioDetails">' in source
    assert "Etichetta selezionata" not in source
    assert "credito wine" not in source and "crediti wine" not in source
    assert "if not selected_master_id and len(master_ids) == 1:" in source


def test_compliance_page_shows_one_section_at_a_time():
    from qrfacile_app.wine_compliance_ui import _SECTION_TABS, _section_tabs_html

    source = (ROOT / "qrfacile_app" / "wine_compliance_ui.py").read_text(encoding="utf-8")
    for _key, _label, ids in _SECTION_TABS:
        for section_id in ids:
            assert f'id="{section_id}"' in source, section_id
    html = _section_tabs_html({"nutrition"})
    assert 'class="qrfSectionTabs"' in html and " hidden>" in html  # visible only with JavaScript
    assert "Avanti: " in html and "qrfSectionHidden" in html
    assert 'data-tab="nutrition" class="done"' in html
    assert "__TABS__" not in html and "__BUTTONS__" not in html
    # the page-tabs bar was removed (the stepper links every page): one nav less
    assert 'class="complianceTabs"' not in source and ">Compliance</a>" not in source


def test_accessibility_names_and_tab_structure_are_present():
    premium = (ROOT / "qrfacile_app" / "premium_ui.py").read_text(encoding="utf-8")
    for field_id, name in (
        ("wine-master-id", "wine_master_id"),
        ("wine-volume-ml", "volume_ml"),
        ("wine-qr-duration", "qr_duration_years"),
    ):
        assert f'for="{field_id}"' in premium
        assert f'id="{field_id}" name="{name}"' in premium

    compliance = (ROOT / "qrfacile_app" / "wine_compliance_ui.py").read_text(encoding="utf-8")
    assert 'role="tablist"' in compliance
    assert "['ArrowLeft', 'ArrowRight', 'Home', 'End']" in compliance
    for name in ("energy_kj", "energy_kcal", "fat", "saturates", "carbs", "sugars", "protein", "salt"):
        field_id = "nutrition-" + name.replace("_", "-")
        assert f'for="{field_id}"' in compliance
        assert f'id="{field_id}" name="{name}"' in compliance


def test_primary_button_and_credit_contrast_use_accessible_colours():
    css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    assert "--accent:#0f766e" in css
    assert ".sidebarCreditGeneric span{ color:#475569; }" in css


def test_score_widget_speaks_plain_italian():
    text = (ROOT / "qrfacile_app" / "compliance_score_middleware.py").read_text(encoding="utf-8")
    for jargon in ("Compliance Score", "<span>PASS</span>", "<span>WARNING</span>", "<span>ERROR</span>", "Compliance Engine"):
        assert jargon not in text
    assert "Tutti i dati obbligatori sono presenti" in text
    assert "suggerimenti facoltativi" in text


def test_published_lot_counts_as_complete_even_without_back_image():
    from qrfacile_app.dashboard_ui import _compliance_badge_html, _dashboard_counts, _next_step

    published = {
        "wine_id": 3, "wine_name": "Falanghina", "winery_name": "Cantina", "slug": "S1",
        "status": "attiva", "ingredient_count": 1, "allergen_count": 1, "nutrition_ok": True,
        "recycle_count": 4, "front_thumb": "f.webp", "back_thumb": "",
    }
    counts = _dashboard_counts([published])
    assert (counts["complete"], counts["incomplete"], counts["published"]) == (1, 0, 1)
    badge = _compliance_badge_html(published)
    assert "Dati obbligatori completi" in badge and "foto del retro" in badge
    label, _text, _href = _next_step([published], "winery")
    assert label == "Tutto pronto"

    draft = dict(published, status="bozza", recycle_count=0, front_thumb="")
    assert _dashboard_counts([draft])["incomplete"] == 1
    assert _next_step([draft], "winery")[0] == "Completa i dati obbligatori"


def test_winery_pages_say_dati_obbligatori_not_compliance():
    for name in ("wine_hub_ui.py", "wine_images_ui.py", "wine_compliance_ui.py", "label_hub_ui.py", "dashboard_ui.py"):
        source = (ROOT / "qrfacile_app" / name).read_text(encoding="utf-8")
        assert ">Compliance</a>" not in source and "<b>Compliance</b>" not in source, name
        assert "Completa compliance" not in source and "Compliance cantina" not in source, name
