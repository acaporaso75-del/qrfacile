from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg

router = APIRouter(prefix="/admin/compliance", tags=["ai-review"])


def _load_pending(limit: int = 100):
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, created_at, user_id, use_case, provider, model,
                       model_version, risk_classification,
                       contains_personal_data, human_review_status, metadata
                FROM ai_usage_log
                WHERE human_review_status = 'pending'
                ORDER BY created_at ASC
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall()


@router.get("/ai-review", response_class=HTMLResponse)
def ai_review_queue(request: Request):
    require_any_role(request, ("admin",))
    try:
        records = _load_pending()
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
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="Decisione non valida")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE ai_usage_log
                   SET human_review_status=%s,
                       reviewer_user_id=%s,
                       reviewed_at=%s
                 WHERE id=%s AND human_review_status='pending'
             RETURNING id, human_review_status
                """,
                (decision, int(user["id"]), datetime.now(timezone.utc), record_id),
            )
            row = cur.fetchone()
        conn.commit()

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
