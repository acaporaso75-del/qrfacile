from __future__ import annotations

from html import escape


STEPS = (
    ("wine", "Dati vino"),
    ("ingredients", "Ingredienti e allergeni"),
    ("nutrition", "Valori nutrizionali"),
    ("images", "Immagini"),
    ("recycling", "Riciclabilità"),
    ("review", "Controllo finale"),
    ("publish", "Preview e pubblicazione"),
)


def completion_from_counts(
    *,
    wine_name: str,
    lot: str,
    has_front_image: bool,
    ingredients: int,
    allergens: int,
    has_energy: bool,
    recycling: int,
    published: bool,
) -> set[str]:
    """Steps that are really complete, from saved data only."""
    done = {
        key
        for key, ok in (
            ("wine", bool(str(wine_name or "").strip() and str(lot or "").strip())),
            ("images", bool(has_front_image)),
            ("ingredients", ingredients > 0 and allergens > 0),
            ("nutrition", bool(has_energy)),
            ("recycling", recycling > 0),
        )
        if ok
    }
    if {"wine", "images", "ingredients", "nutrition", "recycling"} <= done:
        done.add("review")
    if published:
        done.add("publish")
    return done


def completed_steps(wine_id: int) -> set[str]:
    """Load the real step state of a wine; empty set if it cannot be read."""
    try:
        from psycopg.rows import dict_row

        from qrfacile_app.db import pg

        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT qw.wine_name, qw.lot, COALESCE(qi.status, '') AS status,
                      (SELECT COUNT(*) FROM wine_assets a WHERE a.wine_id=qw.id AND a.kind='front')::int AS fronts,
                      (SELECT COUNT(*) FROM wine_ingredients i WHERE i.wine_id=qw.id)::int AS ingredients,
                      (SELECT COUNT(*) FROM wine_allergens al WHERE al.wine_id=qw.id)::int AS allergens,
                      (SELECT COUNT(*) FROM wine_nutrition n WHERE n.wine_id=qw.id
                          AND n.energy_kj IS NOT NULL AND n.energy_kcal IS NOT NULL)::int AS nutrition,
                      (SELECT COUNT(*) FROM wine_recycle_items r WHERE r.wine_id=qw.id
                          AND COALESCE(NULLIF(BTRIM(r.code), ''), '-') <> '-')::int AS recycling
                    FROM qr_wines qw
                    LEFT JOIN qr_items qi ON qi.id = qw.qr_item_id
                    WHERE qw.id=%s
                    LIMIT 1
                    """,
                    (int(wine_id),),
                )
                row = cur.fetchone()
    except Exception:
        return set()
    if not row:
        return set()
    return completion_from_counts(
        wine_name=row.get("wine_name") or "",
        lot=row.get("lot") or "",
        has_front_image=int(row.get("fronts") or 0) > 0,
        ingredients=int(row.get("ingredients") or 0),
        allergens=int(row.get("allergens") or 0),
        has_energy=int(row.get("nutrition") or 0) > 0,
        recycling=int(row.get("recycling") or 0),
        published=str(row.get("status") or "").lower() == "attiva",
    )


def render_guided_stepper(wine_id: int, active: str, completed: set[str] | None = None) -> str:
    done = completed or set()
    links = {
        "wine": f"/app/wine/{wine_id}",
        "images": f"/app/wine/{wine_id}/images",
        "ingredients": f"/app/wine/{wine_id}/compliance#ingredienti",
        "nutrition": f"/app/wine/{wine_id}/compliance#nutrizione",
        "recycling": f"/app/wine/{wine_id}/compliance#riciclabilita",
        "review": f"/app/wine/{wine_id}/review",
        "publish": f"/app/wine/{wine_id}/complete",
    }
    if wine_id <= 0:
        links = {key: ("/app/new-wine" if key == "wine" else "#") for key, _label in STEPS}
    items = []
    for number, (key, label) in enumerate(STEPS, 1):
        classes = "qrfWizardStep"
        state = "Da completare"
        if key in done:
            classes += " complete"
            state = "Completato"
        if key == active:
            classes += " active"
            state = "Passaggio attuale"
        items.append(
            f'<a class="{classes}" href="{links[key]}"><span>{number}</span>'
            f'<b>{escape(label)}</b><small>{state}</small></a>'
        )
    return f"""
    <nav class="qrfWizard" aria-label="Percorso creazione etichetta">
      {''.join(items)}
    </nav>
    <style>
      .qrfWizard{{display:grid;grid-template-columns:repeat(7,minmax(130px,1fr));gap:10px;margin:18px 0;overflow-x:auto;padding-bottom:4px}}
      .qrfWizardStep{{display:grid;grid-template-columns:32px 1fr;column-gap:9px;align-items:center;min-width:140px;padding:12px;border:1px solid rgba(2,8,23,.09);border-radius:17px;background:#fff}}
      .qrfWizardStep span{{grid-row:1/3;display:grid;place-items:center;width:32px;height:32px;border-radius:11px;background:#e2e8f0;font-weight:950}}
      .qrfWizardStep b{{font-size:12px;line-height:1.15}}.qrfWizardStep small{{font-size:10px;color:#64748b}}
      .qrfWizardStep.complete span{{background:#dcfce7;color:#166534}}.qrfWizardStep.active{{border-color:#14b8a6;background:#f0fdfa}}.qrfWizardStep.active span{{background:#14b8a6;color:#fff}}
    </style>
    """
