from __future__ import annotations

from html import escape


STEPS = (
    ("wine", "Dati vino"),
    ("images", "Immagini"),
    ("ingredients", "Ingredienti e allergeni"),
    ("nutrition", "Valori nutrizionali"),
    ("recycling", "Riciclabilità"),
    ("review", "Controllo finale"),
    ("publish", "Preview e pubblicazione"),
)


def render_guided_stepper(wine_id: int, active: str, completed: set[str] | None = None) -> str:
    done = completed or set()
    links = {
        "wine": f"/app/wine/{wine_id}",
        "images": f"/app/wine/{wine_id}/images",
        "ingredients": f"/app/wine/{wine_id}/compliance#ingredienti",
        "nutrition": f"/app/wine/{wine_id}/compliance#nutrizione",
        "recycling": f"/app/wine/{wine_id}/compliance#riciclabilita",
        "review": f"/app/wine/{wine_id}/compliance#controllo-finale",
        "publish": f"/app/wine/{wine_id}/compliance#pubblicazione",
    }
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
