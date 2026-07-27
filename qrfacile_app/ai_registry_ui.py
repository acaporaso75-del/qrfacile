from __future__ import annotations

import html
import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.ai_registry_service import list_ai_systems, upsert_ai_system

router = APIRouter(prefix="/admin/compliance", tags=["ai-registry"])


def _esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@router.get("/ai-systems", response_class=HTMLResponse)
def ai_system_registry_page(request: Request):
    require_any_role(request, ("admin",))
    systems = list_ai_systems()

    rows = []
    for item in systems:
        rows.append(
            "<tr>"
            f"<td>{_esc(item.get('system_key'))}</td>"
            f"<td>{_esc(item.get('name'))}</td>"
            f"<td>{_esc(item.get('provider'))} / {_esc(item.get('model'))}</td>"
            f"<td>{_esc(item.get('risk_classification'))}</td>"
            f"<td>{_esc(item.get('status'))}</td>"
            f"<td>{'Sì' if item.get('human_oversight_required') else 'No'}</td>"
            f"<td>{'Sì' if item.get('auto_publish_allowed') else 'No'}</td>"
            f"<td>{'Sì' if item.get('dpa_verified') else 'No'}</td>"
            "</tr>"
        )

    table_rows = "".join(rows) or '<tr><td colspan="8">Nessun sistema AI registrato.</td></tr>'
    return HTMLResponse(
        f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QRFACILE · Registro sistemi AI</title><link rel="stylesheet" href="/static/app.css">
<style>
body{{background:#f5f7fa}} .wrap{{max-width:1200px;margin:0 auto;padding:28px}}
table{{width:100%;border-collapse:collapse;background:#fff}} th,td{{padding:10px;border:1px solid #ddd;text-align:left}}
.grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}} label{{display:grid;gap:5px;font-weight:700}}
input,textarea,select{{padding:10px;border:1px solid #bbb;border-radius:8px}} textarea{{min-height:90px}} .full{{grid-column:1/-1}}
@media(max-width:800px){{.grid{{grid-template-columns:1fr}}.full{{grid-column:auto}}}}
</style></head><body><main class="wrap">
<h1>Registro dei sistemi AI</h1>
<p>Inventario amministrativo dei casi d’uso AI. I contenuti normativi sensibili richiedono supervisione umana e non possono essere pubblicati automaticamente.</p>
<section class="card"><h2>Registra o aggiorna un sistema</h2>
<form method="post" action="/admin/compliance/ai-systems" class="grid">
<label>Chiave sistema<input name="system_key" required placeholder="es. ingredient_assistant"></label>
<label>Nome<input name="name" required></label>
<label>Fornitore<input name="provider" required></label>
<label>Modello<input name="model" required></label>
<label>Versione modello<input name="model_version"></label>
<label>Classificazione rischio<select name="risk_classification"><option>minimal</option><option selected>limited</option><option>high</option><option>prohibited</option></select></label>
<label>Stato<select name="status"><option selected>draft</option><option>assessment</option><option>approved</option><option>suspended</option><option>retired</option></select></label>
<label>Retention giorni<input name="retention_days" type="number" min="0"></label>
<label class="full">Descrizione<textarea name="description" required></textarea></label>
<label class="full">Finalità prevista<textarea name="intended_purpose" required></textarea></label>
<label class="full">Procedura supervisione umana<textarea name="human_oversight_procedure" required></textarea></label>
<label class="full">Usi vietati<textarea name="prohibited_uses"></textarea></label>
<label>Utenti interessati<input name="affected_users"></label>
<label>Categorie input, separate da virgola<input name="input_data_categories"></label>
<label>Categorie output, separate da virgola<input name="output_categories"></label>
<label>Meccanismo trasferimento<input name="transfer_mechanism"></label>
<label><input type="checkbox" name="contains_personal_data"> Contiene dati personali</label>
<label><input type="checkbox" name="special_category_data_allowed"> Ammette categorie particolari</label>
<label><input type="checkbox" name="transparency_notice_required" checked> Informativa trasparenza richiesta</label>
<label><input type="checkbox" name="human_oversight_required" checked> Supervisione umana richiesta</label>
<label><input type="checkbox" name="auto_publish_allowed"> Pubblicazione automatica consentita</label>
<label><input type="checkbox" name="training_data_reuse_allowed"> Riutilizzo dati per training consentito</label>
<label><input type="checkbox" name="dpa_verified"> DPA verificato</label>
<div class="full"><button class="btn btn-primary" type="submit">Salva nel registro</button></div>
</form></section>
<section class="card" style="margin-top:18px"><h2>Sistemi registrati</h2><div style="overflow:auto"><table>
<thead><tr><th>Chiave</th><th>Nome</th><th>Fornitore/modello</th><th>Rischio</th><th>Stato</th><th>Supervisione</th><th>Auto-publish</th><th>DPA</th></tr></thead>
<tbody>{table_rows}</tbody></table></div></section>
<p style="margin-top:18px"><a class="btn" href="/admin/compliance/ai-review">Coda revisione output AI</a></p>
</main></body></html>"""
    )


@router.post("/ai-systems")
def save_ai_system(
    request: Request,
    system_key: str = Form(...),
    name: str = Form(...),
    description: str = Form(...),
    provider: str = Form(...),
    model: str = Form(...),
    intended_purpose: str = Form(...),
    human_oversight_procedure: str = Form(...),
    model_version: str = Form(""),
    prohibited_uses: str = Form(""),
    affected_users: str = Form(""),
    input_data_categories: str = Form(""),
    output_categories: str = Form(""),
    risk_classification: str = Form("limited"),
    status: str = Form("draft"),
    retention_days: str = Form(""),
    transfer_mechanism: str = Form(""),
    contains_personal_data: str | None = Form(None),
    special_category_data_allowed: str | None = Form(None),
    transparency_notice_required: str | None = Form(None),
    human_oversight_required: str | None = Form(None),
    auto_publish_allowed: str | None = Form(None),
    training_data_reuse_allowed: str | None = Form(None),
    dpa_verified: str | None = Form(None),
):
    user = require_any_role(request, ("admin",))
    payload = {
        "system_key": system_key,
        "name": name,
        "description": description,
        "provider": provider,
        "model": model,
        "model_version": model_version or None,
        "intended_purpose": intended_purpose,
        "human_oversight_procedure": human_oversight_procedure,
        "prohibited_uses": prohibited_uses,
        "affected_users": affected_users,
        "input_data_categories": _split_values(input_data_categories),
        "output_categories": _split_values(output_categories),
        "risk_classification": risk_classification,
        "status": status,
        "retention_days": int(retention_days) if retention_days.strip() else None,
        "transfer_mechanism": transfer_mechanism or None,
        "contains_personal_data": contains_personal_data is not None,
        "special_category_data_allowed": special_category_data_allowed is not None,
        "transparency_notice_required": transparency_notice_required is not None,
        "human_oversight_required": human_oversight_required is not None,
        "auto_publish_allowed": auto_publish_allowed is not None,
        "training_data_reuse_allowed": training_data_reuse_allowed is not None,
        "dpa_verified": dpa_verified is not None,
        "metadata": {"source": "admin_ui", "schema_version": 1},
    }
    row = upsert_ai_system(payload=payload, actor_user_id=int(user["id"]))
    write_audit_event(
        action="ai_system_registry_upserted",
        resource_type="ai_system_registry",
        resource_id=int(row["id"]),
        actor=user,
        request=request,
        metadata={"system_key": system_key, "status": status, "risk_classification": risk_classification},
    )
    return RedirectResponse("/admin/compliance/ai-systems", status_code=303)
