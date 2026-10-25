from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import require_csrf_or_same_origin
from qrfacile_app.csrf_core import csrf_input
from qrfacile_app.services.ai_review_service import (
    VALID_REVIEW_DECISIONS,
    list_pending_ai_reviews,
    review_ai_output_record,
)
from qrfacile_app.ui_shell import esc

router = APIRouter(prefix="/admin/compliance", tags=["ai-review"])
logger = logging.getLogger("qrfacile.ai_review")


@router.get("/ai-review", response_class=HTMLResponse)
def ai_review_queue(request: Request):
    require_any_role(request, ("admin",))
    try:
        records = list_pending_ai_reviews()
    except Exception:
        logger.exception("Impossibile caricare la coda di revisione AI")
        raise HTTPException(status_code=503, detail="Schema compliance non disponibile")

    rows = []
    for item in records:
        personal = "Sì" if item.get("contains_personal_data") else "No"
        record_id = int(item["id"])
        rows.append(f"""
        <tr>
          <td>{record_id}</td><td>{esc(str(item.get('created_at') or ''))}</td><td>{esc(str(item.get('use_case') or ''))}</td>
          <td>{esc(str(item.get('provider') or ''))} / {esc(str(item.get('model') or ''))}</td><td>{esc(str(item.get('risk_classification') or ''))}</td>
          <td>{personal}</td>
          <td>
            <form method="post" action="/admin/compliance/ai-review/{record_id}" style="display:flex;gap:8px">
              {csrf_input(request)}
              <button name="decision" value="approved" type="submit">Approva</button>
              <button name="decision" value="rejected" type="submit">Rifiuta</button>
            </form>
          </td>
        </tr>
        """)

    table_rows = "".join(rows) or '<tr><td colspan="7">Nessun output AI in attesa.</td></tr>'
    html = f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1"><title>Revisione AI</title>
    <style>body{{font-family:Arial;padding:28px;background:#f5f7fa}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:12px;border:1px solid #ddd;text-align:left}}button{{padding:8px 12px}}</style>
    </head><body><h1>Revisione umana output AI</h1><p>La pubblicazione resta vietata finché lo stato non è approvato.</p>
    <table><thead><tr><th>ID</th><th>Data</th><th>Caso d’uso</th><th>Modello</th><th>Rischio</th><th>Dati personali</th><th>Azione</th></tr></thead>
    <tbody>{table_rows}</tbody></table></body></html>"""
    return HTMLResponse(html)


@router.post("/ai-review/{record_id}")
def review_ai_output(request: Request, record_id: int, decision: str = Form(...)):
    require_csrf_or_same_origin(request)
    user = require_any_role(request, ("admin",))
    if decision not in VALID_REVIEW_DECISIONS:
        raise HTTPException(status_code=422, detail="Decisione non valida")

    try:
        row = review_ai_output_record(
            record_id=record_id,
            reviewer_user_id=int(user["id"]),
            decision=decision,
        )
    except ValueError as exc:
        if str(exc) == "prohibited_risk_cannot_be_approved":
            raise HTTPException(status_code=422, detail="Un output classificato come proibito non può essere approvato")
        raise HTTPException(status_code=422, detail="Decisione non valida")

    if not row:
        raise HTTPException(status_code=404, detail="Record non trovato o già revisionato")

    write_audit_event(
        action=f"ai_output_{decision}",
        resource_type="ai_usage_log",
        resource_id=record_id,
        actor=user,
        request=request,
    )
    return RedirectResponse("/admin/compliance/ai-review", status_code=303)
