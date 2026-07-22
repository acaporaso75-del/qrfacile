# /opt/qrfacile/qrfacile_app/admin_override_requests_ui.py
import time

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, pill, esc

router = APIRouter()


def now() -> int:
    return int(time.time())


def _balances(cur, user_id: int) -> dict:
    cur.execute(
        """
        SELECT credit_type, COALESCE(SUM(delta),0) AS bal
        FROM credit_ledger
        WHERE user_id=%s
        GROUP BY credit_type
        """,
        (int(user_id),),
    )

    out = {"wine": 0, "generic": 0}

    for r in (cur.fetchall() or []):
        ct = (r.get("credit_type") or "").strip().lower()
        if ct:
            out[ct] = int(r.get("bal") or 0)

    return out


def _status_pill(status: str) -> str:
    s = (status or "").strip().lower()

    if s == "pending":
        return pill("In attesa", "warn")

    if s == "reviewed":
        return pill("Gestita", "green")

    if s == "rejected":
        return pill("Rifiutata", "muted")

    return pill(s or "-", "muted")


@router.get("/admin/override-requests", response_class=HTMLResponse)
def override_requests_page(request: Request, status: str = "pending"):
    user = require_any_role(request, ("admin",))
    uid = int(user["id"])

    status = (status or "pending").strip().lower()
    allowed_status = {"pending", "reviewed", "rejected", "all"}

    if status not in allowed_status:
        status = "pending"

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            balances = _balances(cur, uid)

            where = ""
            params = []

            if status != "all":
                where = "WHERE por.status=%s"
                params.append(status)

            cur.execute(
                f"""
                SELECT
                  por.id,
                  por.wine_id,
                  por.winery_id,
                  por.requested_by_user_id,
                  por.status,
                  por.missing_fields,
                  por.reason,
                  por.created_at,
                  por.updated_at,
                  por.reviewed_at,
                  qw.wine_name,
                  qw.lot,
                  qw.vintage,
                  w.name AS winery_name,
                  u.email AS requested_by_email
                FROM publish_override_requests por
                JOIN qr_wines qw ON qw.id = por.wine_id
                JOIN wineries w ON w.id = por.winery_id
                LEFT JOIN users u ON u.id = por.requested_by_user_id
                {where}
                ORDER BY
                  CASE WHEN por.status='pending' THEN 0 ELSE 1 END,
                  por.updated_at DESC,
                  por.id DESC
                LIMIT 300
                """,
                tuple(params),
            )

            rows = cur.fetchall() or []

    actions = (
        pill(f"wine: {balances.get('wine', 0)}", "green") + " " +
        pill(f"generic: {balances.get('generic', 0)}") + " " +
        top_actions(
            ("/admin", "Admin"),
            ("/app/dashboard", "Dashboard"),
            ("/logout", "Logout"),
        )
    )

    tabs = f"""
    <div class="overrideTabs">
      <a class="overrideTab {'active' if status == 'pending' else ''}" href="/admin/override-requests?status=pending">In attesa</a>
      <a class="overrideTab {'active' if status == 'reviewed' else ''}" href="/admin/override-requests?status=reviewed">Gestite</a>
      <a class="overrideTab {'active' if status == 'rejected' else ''}" href="/admin/override-requests?status=rejected">Rifiutate</a>
      <a class="overrideTab {'active' if status == 'all' else ''}" href="/admin/override-requests?status=all">Tutte</a>
    </div>
    """

    if rows:
        rows_html = ""

        for r in rows:
            req_id = int(r["id"])
            wine_id = int(r["wine_id"])
            st = (r.get("status") or "").strip().lower()
            wine_name = r.get("wine_name") or "-"
            winery_name = r.get("winery_name") or "-"
            lot = r.get("lot") or "-"
            vintage = str(r.get("vintage") or "").strip()
            requested_by = r.get("requested_by_email") or "-"
            missing_fields = r.get("missing_fields") or "-"
            reason = r.get("reason") or ""
            created_at = int(r.get("created_at") or 0)

            created_txt = "-"
            if created_at:
                try:
                    created_txt = time.strftime("%d/%m/%Y %H:%M", time.localtime(created_at))
                except Exception:
                    created_txt = "-"

            manage_forms = ""

            if st == "pending":
                manage_forms = f"""
                <form method="post" action="/admin/override-requests/{req_id}/mark-reviewed" style="display:inline">
                  <button class="btn btn-primary" type="submit">Segna gestita</button>
                </form>

                <form method="post" action="/admin/override-requests/{req_id}/reject" style="display:inline"
                      onsubmit="return confirm('Rifiutare questa richiesta di sblocco?');">
                  <button class="btn btn-danger-soft" type="submit">Rifiuta</button>
                </form>
                """

            vintage_html = f" · Annata {esc(vintage)}" if vintage else ""

            rows_html += f"""
            <article class="card overrideCard">
              <div class="overrideCardMain">
                <div>
                  <div class="overrideTitle">
                    {esc(wine_name)}
                    {_status_pill(st)}
                  </div>

                  <div class="overrideMeta">
                    {esc(winery_name)} · Lotto {esc(lot)}{vintage_html}
                  </div>

                  <div class="overrideInfoGrid">
                    <div>
                      <span>Richiesta da</span>
                      <b>{esc(requested_by)}</b>
                    </div>

                    <div>
                      <span>Data richiesta</span>
                      <b>{esc(created_txt)}</b>
                    </div>

                    <div>
                      <span>Dati mancanti</span>
                      <b>{esc(missing_fields)}</b>
                    </div>
                  </div>

                  <div class="overrideReason">
                    <span>Motivo</span>
                    <div>{esc(reason) if reason else "Nessun motivo indicato."}</div>
                  </div>
                </div>

                <div class="overrideActions">
                  <a class="btn" href="/app/wine/{wine_id}">Apri lotto</a>
                  <a class="btn" href="/app/wine/{wine_id}/compliance">Compliance</a>
                  {manage_forms}
                </div>
              </div>
            </article>
            """
    else:
        rows_html = """
        <div class="card overrideEmpty">
          <div class="overrideEmptyIcon">✅</div>
          <div>
            <div class="h2">Nessuna richiesta trovata</div>
            <div class="p">Non ci sono richieste di sblocco per il filtro selezionato.</div>
          </div>
        </div>
        """

    body = f"""
    <section class="overrideWrap">
      <div class="overrideHero">
        <div>
          <div class="overrideEyebrow">Back office</div>
          <div class="h1">Richieste sblocco pubblicazione</div>
          <div class="p">
            Qui vedi le richieste delle cantine che vogliono pubblicare un QR anche se i dati obbligatori risultano incompleti.
            L’admin valuta, apre il lotto e decide se forzare la pubblicazione.
          </div>
        </div>

        <div class="overrideHeroBox">
          <span>Richieste visualizzate</span>
          <b>{len(rows)}</b>
        </div>
      </div>

      {tabs}

      <div class="overrideList">
        {rows_html}
      </div>

      <style>
        .overrideWrap {{
          max-width:1180px;
          margin:0 auto;
        }}

        .overrideHero {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:28px;
          overflow:hidden;
          box-shadow:0 24px 80px rgba(2,8,23,.08);
          background:
            radial-gradient(circle at 8% 12%, rgba(191,245,230,.58), transparent 34%),
            radial-gradient(circle at 92% 8%, rgba(207,232,255,.58), transparent 34%),
            linear-gradient(135deg,rgba(255,255,255,.96),rgba(248,252,250,.92));
          padding:30px;
          display:grid;
          grid-template-columns:minmax(0,1fr) 220px;
          gap:24px;
          align-items:end;
        }}

        .overrideEyebrow {{
          display:inline-flex;
          padding:7px 12px;
          border-radius:999px;
          background:rgba(20,184,166,.10);
          color:#0f766e;
          font-size:12px;
          font-weight:950;
          letter-spacing:.08em;
          text-transform:uppercase;
        }}

        .overrideHeroBox {{
          border:1px solid rgba(2,8,23,.07);
          background:rgba(255,255,255,.72);
          border-radius:22px;
          padding:18px;
        }}

        .overrideHeroBox span {{
          display:block;
          font-size:12px;
          color:#64748b;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.07em;
        }}

        .overrideHeroBox b {{
          display:block;
          margin-top:8px;
          font-size:38px;
          line-height:1;
          font-weight:950;
        }}

        .overrideTabs {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:18px;
        }}

        .overrideTab {{
          display:inline-flex;
          align-items:center;
          justify-content:center;
          padding:12px 16px;
          border-radius:18px;
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.76);
          font-weight:950;
          box-shadow:0 12px 30px rgba(2,8,23,.04);
        }}

        .overrideTab.active {{
          background:linear-gradient(135deg,rgba(191,245,230,.95),rgba(207,232,255,.88));
          border-color:rgba(20,184,166,.18);
        }}

        .overrideList {{
          display:grid;
          gap:14px;
          margin-top:18px;
        }}

        .overrideCard {{
          padding:22px;
        }}

        .overrideCardMain {{
          display:grid;
          grid-template-columns:minmax(0,1fr) auto;
          gap:18px;
          align-items:flex-start;
        }}

        .overrideTitle {{
          display:flex;
          gap:10px;
          align-items:center;
          flex-wrap:wrap;
          font-size:22px;
          font-weight:950;
          letter-spacing:-.35px;
        }}

        .overrideMeta {{
          margin-top:8px;
          color:#64748b;
          font-weight:800;
        }}

        .overrideInfoGrid {{
          display:grid;
          grid-template-columns:repeat(3,minmax(0,1fr));
          gap:10px;
          margin-top:16px;
        }}

        .overrideInfoGrid div {{
          border:1px solid rgba(2,8,23,.07);
          background:rgba(255,255,255,.70);
          border-radius:18px;
          padding:12px;
          min-width:0;
        }}

        .overrideInfoGrid span,
        .overrideReason span {{
          display:block;
          color:#64748b;
          font-size:11px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.06em;
        }}

        .overrideInfoGrid b {{
          display:block;
          margin-top:5px;
          font-size:13px;
          font-weight:900;
          word-break:break-word;
        }}

        .overrideReason {{
          margin-top:12px;
          border:1px solid rgba(2,8,23,.07);
          background:rgba(255,255,255,.70);
          border-radius:18px;
          padding:12px;
        }}

        .overrideReason div {{
          margin-top:6px;
          color:#334155;
          font-size:13px;
          font-weight:750;
          line-height:1.45;
        }}

        .overrideActions {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          justify-content:flex-end;
          align-items:flex-start;
          min-width:250px;
        }}

        .overrideEmpty {{
          display:flex;
          gap:16px;
          align-items:flex-start;
        }}

        .overrideEmptyIcon {{
          width:58px;
          height:58px;
          border-radius:20px;
          display:flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.85),rgba(207,232,255,.85));
          font-size:26px;
          flex:0 0 auto;
        }}

        @media(max-width:980px) {{
          .overrideHero,
          .overrideCardMain,
          .overrideInfoGrid {{
            grid-template-columns:1fr;
          }}

          .overrideActions {{
            justify-content:flex-start;
            min-width:0;
          }}
        }}

        @media(max-width:560px) {{
          .overrideHero,
          .overrideCard {{
            padding:22px;
          }}

          .overrideActions .btn,
          .overrideActions form,
          .overrideActions button {{
            width:100%;
          }}
        }}
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Richieste sblocco",
        subtitle="Back office",
        body_html=body,
        actions_html=actions,
        role="admin",
        user_email=user.get("email", ""),
        credits=balances,
    ))


@router.post("/admin/override-requests/{request_id}/mark-reviewed")
def mark_reviewed(request: Request, request_id: int):
    user = require_any_role(request, ("admin",))

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE publish_override_requests
                SET status='reviewed',
                    reviewed_by_user_id=%s,
                    reviewed_at=%s,
                    updated_at=%s
                WHERE id=%s
                """,
                (int(user["id"]), now(), now(), int(request_id)),
            )

            if cur.rowcount == 0:
                raise HTTPException(404, "Richiesta non trovata")

            conn.commit()

    return RedirectResponse("/admin/override-requests?status=pending", status_code=303)


@router.post("/admin/override-requests/{request_id}/reject")
def reject_request(request: Request, request_id: int):
    user = require_any_role(request, ("admin",))

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE publish_override_requests
                SET status='rejected',
                    reviewed_by_user_id=%s,
                    reviewed_at=%s,
                    updated_at=%s
                WHERE id=%s
                """,
                (int(user["id"]), now(), now(), int(request_id)),
            )

            if cur.rowcount == 0:
                raise HTTPException(404, "Richiesta non trovata")

            conn.commit()

    return RedirectResponse("/admin/override-requests?status=pending", status_code=303)
