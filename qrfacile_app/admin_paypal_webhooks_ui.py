from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import esc, page, pill, top_actions


router = APIRouter()
_RESOLUTIONS = {"acknowledged", "resolved_external", "false_positive"}


def _status(value: object, reviewed_at: object) -> str:
    status = str(value or "").strip().lower()
    if reviewed_at:
        return pill("Gestito", "green")
    if status in {"manual_review", "failed"}:
        return pill("Da verificare", "warn")
    if status == "processed":
        return pill("Elaborato", "green")
    return pill(status or "-", "muted")


@router.get("/admin/paypal-webhooks", response_class=HTMLResponse)
def paypal_webhooks_page(request: Request, view: str = "open"):
    user = require_any_role(request, ("admin",))
    selected = view if view in {"open", "resolved", "all"} else "open"

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT e.id, e.event_id, e.event_type, e.payment_environment,
                       e.verification_status, e.order_id, e.resource_id,
                       e.failure_code, e.received_at, e.reviewed_at,
                       e.review_resolution, e.review_notes, u.email AS reviewer_email
                FROM paypal_webhook_events e
                LEFT JOIN users u ON u.id=e.reviewed_by_user_id
                WHERE %s = 'all'
                   OR (%s = 'open'
                       AND e.verification_status IN ('manual_review','failed')
                       AND e.reviewed_at IS NULL)
                   OR (%s = 'resolved' AND e.reviewed_at IS NOT NULL)
                ORDER BY e.received_at DESC, e.id DESC
                LIMIT 200
                """,
                (selected, selected, selected),
            )
            rows = cur.fetchall() or []

    cards = []
    for row in rows:
        review_form = ""
        if not row.get("reviewed_at") and row.get("verification_status") in {"manual_review", "failed"}:
            review_form = f"""
            <form method="post" action="/admin/paypal-webhooks/{int(row['id'])}/review"
                  style="display:grid;gap:8px;margin-top:12px">
              <label>Esito revisione
                <select name="resolution" required>
                  <option value="acknowledged">Preso in carico</option>
                  <option value="resolved_external">Risolto sul provider</option>
                  <option value="false_positive">Falso positivo</option>
                </select>
              </label>
              <label>Nota operativa
                <textarea name="notes" maxlength="1000" required></textarea>
              </label>
              <button class="btn btn-primary" type="submit">Registra revisione</button>
            </form>
            """
        cards.append(
            f"""
            <article class="card" style="margin-top:12px">
              <div class="row" style="justify-content:space-between">
                <strong>{esc(row.get('event_type') or '-')}</strong>
                {_status(row.get('verification_status'), row.get('reviewed_at'))}
              </div>
              <p class="muted">Evento {esc(row.get('event_id') or '-')} · ambiente {esc(row.get('payment_environment') or '-')}</p>
              <p>Ordine interno: {esc(row.get('order_id') or '-')} · risorsa PayPal: {esc(row.get('resource_id') or '-')}</p>
              <p>Errore/stato: {esc(row.get('failure_code') or '-')}</p>
              <p class="muted">Ricevuto: {esc(row.get('received_at') or '-')}</p>
              {f"<p>Revisione: {esc(row.get('review_resolution') or '-')} · {esc(row.get('reviewer_email') or '-')}</p><p>{esc(row.get('review_notes') or '')}</p>" if row.get('reviewed_at') else ''}
              {review_form}
            </article>
            """
        )

    actions = top_actions(
        ("/admin/paypal-webhooks?view=open", "Aperti"),
        ("/admin/paypal-webhooks?view=resolved", "Gestiti"),
        ("/admin/paypal-webhooks?view=all", "Tutti"),
        ("/admin", "Admin"),
    )
    body = "".join(cards) or '<div class="card"><p>Nessun evento in questa vista.</p></div>'
    return HTMLResponse(page(
        title="QRFACILE · Eventi PayPal",
        subtitle="Riconciliazione webhook",
        body_html=body,
        actions_html=actions,
        role="admin",
        user_email=user.get("email", ""),
        credits=None,
    ))


@router.post("/admin/paypal-webhooks/{event_id}/review")
def review_paypal_webhook(
    request: Request,
    event_id: int,
    resolution: str = Form(...),
    notes: str = Form(...),
):
    require_csrf_or_same_origin(request)
    user = require_any_role(request, ("admin",))
    chosen = resolution.strip().lower()
    clean_notes = notes.strip()
    if chosen not in _RESOLUTIONS or not clean_notes or len(clean_notes) > 1000:
        raise HTTPException(422, "Esito o nota non validi")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE paypal_webhook_events
                SET reviewed_at=now(), reviewed_by_user_id=%s,
                    review_resolution=%s, review_notes=%s
                WHERE id=%s
                  AND verification_status IN ('manual_review','failed')
                  AND reviewed_at IS NULL
                RETURNING event_id, event_type, order_id
                """,
                (int(user["id"]), chosen, clean_notes, int(event_id)),
            )
            reviewed = cur.fetchone()
            if not reviewed:
                raise HTTPException(404, "Evento non trovato o già gestito")
            cur.execute(
                """
                INSERT INTO audit_log (
                    user_id, role, action, entity_type, entity_id,
                    ip, user_agent, meta, created_at
                ) VALUES (
                    %s, 'admin', 'paypal_webhook_reviewed', 'orders', %s,
                    NULL, 'admin-paypal-webhooks',
                    jsonb_build_object(
                        'event_id', %s,
                        'event_type', %s,
                        'resolution', %s
                    ), now()
                )
                """,
                (
                    int(user["id"]),
                    reviewed.get("order_id"),
                    reviewed["event_id"],
                    reviewed["event_type"],
                    chosen,
                ),
            )
            conn.commit()
    return RedirectResponse("/admin/paypal-webhooks?view=open", status_code=303)
