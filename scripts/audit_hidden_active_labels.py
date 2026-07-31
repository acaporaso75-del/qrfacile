#!/usr/bin/env python3
"""List active labels currently hidden by the public compliance gate (read-only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.publish_routes import _publication_missing_fields
from qrfacile_app.services.recycling_catalog import normalize_recycling_items
from qrfacile_app.services.wine_compliance_explainability import run_explainable_wine_compliance


def _compliance_payload(cur, wine_id: int) -> dict:
    cur.execute(
        """SELECT qw.id AS wine_id, qw.wine_name, qw.vintage, qw.lot, w.name AS winery_name
           FROM qr_wines qw JOIN wineries w ON w.id=qw.winery_id WHERE qw.id=%s""",
        (wine_id,),
    )
    wine = cur.fetchone() or {}
    cur.execute(
        """SELECT energy_kj, energy_kcal, fat, saturates, carbs, sugars, protein, salt
           FROM wine_nutrition WHERE wine_id=%s LIMIT 1""",
        (wine_id,),
    )
    nutrition = cur.fetchone() or {}
    cur.execute(
        """SELECT im.name FROM wine_ingredients wi
           JOIN ingredients_master im ON im.id=wi.ingredient_id
           WHERE wi.wine_id=%s ORDER BY lower(im.name)""",
        (wine_id,),
    )
    ingredients = [row["name"] for row in (cur.fetchall() or []) if row.get("name")]
    cur.execute(
        """SELECT COALESCE(am.name, wa.custom_text) AS name FROM wine_allergens wa
           LEFT JOIN allergens_master am ON am.id=wa.allergen_id
           WHERE wa.wine_id=%s ORDER BY COALESCE(am.name, wa.custom_text)""",
        (wine_id,),
    )
    allergens = [row["name"] for row in (cur.fetchall() or []) if row.get("name")]
    cur.execute(
        "SELECT contains_sulfites, contains_egg, contains_milk FROM qr_wines WHERE id=%s",
        (wine_id,),
    )
    flags = cur.fetchone() or {}
    for enabled, name in (("contains_sulfites", "solfiti"), ("contains_egg", "uova"), ("contains_milk", "latte")):
        if flags.get(enabled) and name not in allergens:
            allergens.append(name)
    cur.execute(
        """SELECT component, product, code, extra_code, note FROM wine_recycle_items
           WHERE wine_id=%s ORDER BY component""",
        (wine_id,),
    )
    recycle = normalize_recycling_items({row["component"]: dict(row) for row in (cur.fetchall() or [])})
    cur.execute(
        "SELECT extra_ingredients, story_text, public_theme FROM wine_meta WHERE wine_id=%s LIMIT 1",
        (wine_id,),
    )
    return {
        "wine": dict(wine), "nutrition": dict(nutrition), "ingredients": ingredients,
        "allergens": allergens, "recycle": recycle, "meta": dict(cur.fetchone() or {}),
    }


def main() -> int:
    hidden: list[dict] = []
    with pg() as conn:
        conn.read_only = True
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT qi.slug, qw.id AS wine_id
                   FROM qr_items qi
                   JOIN qr_wines qw ON qw.qr_item_id=qi.id
                   WHERE lower(trim(COALESCE(qi.status, '')))='attiva'
                   ORDER BY qi.slug"""
            )
            active = list(cur.fetchall() or [])
            for row in active:
                wine_id = int(row["wine_id"])
                reasons = _publication_missing_fields(cur, wine_id)
                report = run_explainable_wine_compliance(_compliance_payload(cur, wine_id))
                blocking = [
                    item["title"] for item in report["results"]
                    if item.get("status") == "ERROR" and item.get("blocking")
                ]
                warnings = [
                    item["title"] for item in report["results"] if item.get("status") == "WARNING"
                ]
                reasons.extend(title for title in blocking if title not in reasons)
                if reasons:
                    hidden.append({
                        "slug": row["slug"],
                        "wine_id": wine_id,
                        "reasons": reasons,
                        "warnings_to_verify": warnings,
                    })
        conn.rollback()

    print(json.dumps({"hidden_count": len(hidden), "labels": hidden}, ensure_ascii=False, indent=2))
    return 1 if hidden else 0


if __name__ == "__main__":
    raise SystemExit(main())
