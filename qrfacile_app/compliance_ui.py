from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page_public

router = APIRouter(tags=["compliance"])

AI_POLICY_VERSION = "2026-07-23"


def _table_exists(cur, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) AS name", (f"public.{table_name}",))
    row = cur.fetchone() or {}
    return bool(row.get("name"))


@router.get("/ai-policy", response_class=HTMLResponse)
def ai_policy(request: Request):
    body = f"""
    <section style="max-width:980px;margin:0 auto">
      <div class="card">
        <div class="h1">Trasparenza e utilizzo dell’intelligenza artificiale</div>
        <div class="p">Versione {AI_POLICY_VERSION}</div>
      </div>
      <div class="card" style="margin-top:14px">
        <div class="h2">Ruolo dell’AI</div>
        <div class="p">Le funzioni AI di QRFACILE, quando attive, assistono la compilazione e il controllo. Non sostituiscono la valutazione professionale né certificano la conformità normativa.</div>
        <div class="h2" style="margin-top:18px">Supervisione umana</div>
        <div class="p">Ingredienti, allergeni, dichiarazioni nutrizionali, claim, traduzioni e contenuti destinati alla pubblicazione richiedono approvazione umana prima dell’uso.</div>
        <div class="h2" style="margin-top:18px">Dati e fornitori</div>
        <div class="p">QRFACILE limita i dati trasmessi ai fornitori AI, registra il caso d’uso e la versione del modello e vieta l’uso dei dati cliente per addestramento salvo accordo espresso e documentato.</div>
        <div class="h2" style="margin-top:18px">Contestazioni</div>
        <div class="p">Gli utenti possono segnalare output errati, richiedere revisione e ripristinare contenuti precedenti. Gli output AI non devono essere pubblicati automaticamente.</div>
      </div>
    </section>
    """
    return HTMLResponse(page_public(
        title="QRFACILE · AI Policy",
        subtitle="AI Policy",
        body_html=body,
        actions_html='<a class="btn" href="/legal">Note legali</a><a class="btn" href="/privacy">Privacy</a>',
    ))


@router.get("/api/admin/compliance/status")
def compliance_status(request: Request):
    require_any_role(request, ("admin",))

    required_tables = (
        "legal_documents",
        "legal_acceptances",
        "audit_log",
        "ai_usage_log",
        "compliance_incidents",
    )
    tables: dict[str, bool] = {}

    try:
        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                for name in required_tables:
                    tables[name] = _table_exists(cur, name)
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": "database_unavailable", "detail": str(exc)},
        )

    return {
        "ok": all(tables.values()),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ai_policy_version": AI_POLICY_VERSION,
        "tables": tables,
        "tracking_on_elabel_pages_allowed": False,
        "human_review_required_for_ai": True,
    }


@router.post("/api/admin/compliance/ai-usage")
async def register_ai_usage(request: Request):
    user = require_any_role(request, ("admin", "winery", "studio"))
    payload: dict[str, Any] = await request.json()

    required = ("use_case", "provider", "model", "input", "output")
    missing = [key for key in required if not payload.get(key)]
    if missing:
        raise HTTPException(status_code=422, detail=f"Campi mancanti: {', '.join(missing)}")

    input_text = json.dumps(payload["input"], ensure_ascii=False, sort_keys=True)
    output_text = json.dumps(payload["output"], ensure_ascii=False, sort_keys=True)
    input_sha = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
    output_sha = hashlib.sha256(output_text.encode("utf-8")).hexdigest()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if not _table_exists(cur, "ai_usage_log"):
                raise HTTPException(status_code=503, detail="Schema compliance non installato")

            cur.execute(
                """
                INSERT INTO ai_usage_log (
                    user_id, use_case, provider, model, model_version,
                    input_sha256, output_sha256, prompt_template_version,
                    risk_classification, contains_personal_data,
                    human_review_required, human_review_status, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    true, 'pending', %s::jsonb
                )
                RETURNING id, created_at, human_review_status
                """,
                (
                    int(user["id"]),
                    str(payload["use_case"]),
                    str(payload["provider"]),
                    str(payload["model"]),
                    payload.get("model_version"),
                    input_sha,
                    output_sha,
                    payload.get("prompt_template_version"),
                    str(payload.get("risk_classification") or "limited"),
                    bool(payload.get("contains_personal_data", False)),
                    json.dumps(payload.get("metadata") or {}, ensure_ascii=False),
                ),
            )
            row = cur.fetchone()
        conn.commit()

    return {"ok": True, "record": row}
