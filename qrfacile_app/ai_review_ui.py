from __future__ import annotations

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.ai_review_service import (
    VALID_REVIEW_DECISIONS,
    list_pending_ai_reviews,
    review_ai_output_record,
)

router = APIRouter(prefix="/admin/compliance", tags=["ai-review"])


@router.get("/ai-review", response_class=HTMLResponse)
def ai_review_queue(request: Request):
    require_any_role(request, ("admin",))
    try:
        records = list_pending_ai_reviews()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Schema compliance non disponibile: {exc}")

    rows = []
    for item in records:
        personal = "Sì" if item.get("contains_personal_data") else "No"
        rows.append(f"""
        <tr>
          <td>{item['id']}</td><td>{item['created_at']}</td><td>{item['use_case']}</td>
          <td>{item['provider']} / {item['model']}</td><td>{item['risk_classification']}</td>
          <td>{personal}</td>
          <td>
            <form method="post" action="/admin/compliance/ai-review/{item['id']}" style="display:flex;gap:8px">
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
    user = require_any_role(request, ("admin",))
    if decision not in VALID_REVIEW_DECISIONS:
        raise HTTPException(status_code=422, detail="Decisione non valida")

    try:
        row = review_ai_output_record(
            record_id=record_id,
            reviewer_user_id=int(user["id"]),
            decision=decision,
        )
    except ValueError:
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
