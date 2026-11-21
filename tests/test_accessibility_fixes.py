"""Accessibility regressions found by axe-core 4.10.2 on staging 0afb234."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ratio(fg: str, bg: str) -> float:
    def lum(hex_color: str) -> float:
        h = hex_color.lstrip("#")
        channels = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    a, b = lum(fg), lum(bg)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def _css_var(name: str) -> str:
    css = (ROOT / "static" / "app.css").read_text(encoding="utf-8")
    return re.search(rf"--{name}:(#[0-9a-fA-F]{{6}});", css).group(1)


def test_primary_buttons_and_muted_text_meet_wcag_aa_contrast():
    assert _ratio("#ffffff", _css_var("accent")) >= 4.5
    for background in ("#ffffff", "#ecfdf5", "#eff6ff", "#f5f7fb", "#eef3f8"):
        assert _ratio(_css_var("muted"), background) >= 4.5, background


def test_white_numbers_on_teal_badges_meet_contrast():
    for name in ("dashboard_ui.py", "guided_flow.py", "wine_compliance_ui.py"):
        source = (ROOT / "qrfacile_app" / name).read_text(encoding="utf-8")
        assert "background:#14b8a6;color:#fff" not in source, name


def _labelled(source: str, field: str) -> bool:
    match = re.search(rf'<(?:input|select|textarea)\b[^>]*\bid="([^"]+)"[^>]*\bname="{field}"', source)
    return bool(match) and f'for="{match.group(1)}"' in source


def test_new_lot_fields_have_programmatic_labels():
    source = (ROOT / "qrfacile_app" / "premium_ui.py").read_text(encoding="utf-8")
    for field in ("wine_master_id", "vintage", "lot", "volume_ml", "alcohol", "qr_duration_years"):
        assert _labelled(source, field), field


def test_nutrition_fields_have_programmatic_labels_and_unique_ids():
    source = (ROOT / "qrfacile_app" / "wine_compliance_ui.py").read_text(encoding="utf-8")
    for field in ("energy_kj", "energy_kcal", "fat", "saturates", "carbs", "sugars", "protein", "salt"):
        assert _labelled(source, field), field
    ids = re.findall(r'\bid="(f-[^"]+)"', source)
    assert len(ids) == len(set(ids))


def test_section_tabs_are_inside_a_tablist():
    from qrfacile_app.wine_compliance_ui import _section_tabs_html

    assert 'role="tablist"' in _section_tabs_html(set())


def test_dashboard_search_fields_are_labelled():
    source = (ROOT / "qrfacile_app" / "dashboard_ui.py").read_text(encoding="utf-8")
    assert 'for="dash-q"' in source and 'id="dash-q"' in source
    assert 'for="dash-work"' in source and 'id="dash-work"' in source
