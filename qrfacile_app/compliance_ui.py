from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.compliance_service import (
    AI_POLICY_VERSION,
    get_compliance_status,
    register_ai_usage_record,
)
from qrfacile_app.ui_shell import page_public

router = APIRouter(tags=["compliance"])


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
    try:
        return get_compliance_status()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": "database_unavailable", "detail": str(exc)},
        )


@router.post("/api/admin/compliance/ai-usage")
async def register_ai_usage(request: Request):
    user = require_any_role(request, ("admin", "winery", "studio"))
    payload: dict[str, Any] = await request.json()
    record = register_ai_usage_record(user_id=int(user["id"]), payload=payload)
    return {"ok": True, "record": record}
