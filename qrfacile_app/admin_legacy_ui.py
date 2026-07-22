from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, esc, pill

router = APIRouter()


@router.get("/admin/legacy", response_class=HTMLResponse)
def admin_legacy_pages(request: Request, q: str = ""):
    user = require_any_role(request, ("admin",))

    q = (q or "").strip()

    where = "TRUE"
    params = []

    if q:
        where += """
        AND (
          lower(slug) LIKE %s
          OR lower(title) LIKE %s
          OR lower(source_url) LIKE %s
        )
        """
        like = f"%{q.lower()}%"
        params.extend([like, like, like])

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT id, wp_id, slug, title, source_url, active, updated_at
                FROM legacy_pages
                WHERE {where}
                ORDER BY wp_id NULLS LAST, slug
                """,
                tuple(params),
            )
            rows = cur.fetchall() or []

    cards = ""

    for r in rows:
        active = bool(r.get("active"))
        active_badge = pill("Attiva", "green") if active else pill("Disattivata", "muted")
        slug = (r.get("slug") or "").strip()
        title = r.get("title") or slug
        source_url = r.get("source_url") or ""
        wp_id = r.get("wp_id") or "-"

        cards += f"""
        <div class="legacyRow">
          <div class="legacyMain">
            <div class="legacyTitle">
              {esc(title)}
              {active_badge}
            </div>

            <div class="legacyMeta">
              WP ID {esc(str(wp_id))} · 
              <span class="mono">/{esc(slug)}/</span>
            </div>

            <div class="legacySource">
              Origine: {esc(source_url or "-")}
            </div>
          </div>

          <div class="legacyActions">
            <a class="btn btn-primary" href="/{esc(slug)}/" target="_blank">Apri nuovo</a>
            {f'<a class="btn" href="{esc(source_url)}" target="_blank">Apri vecchio</a>' if source_url else ''}
          </div>
        </div>
        """

    if not cards:
        cards = """
        <div class="card">
          <div class="h2">Nessun risultato</div>
          <div class="p">Nessuna pagina legacy trovata con questi filtri.</div>
        </div>
        """

    actions = top_actions(
        ("/admin", "Admin"),
        ("/app/start", "Menu"),
        ("/logout", "Logout"),
    )

    body = f"""
    <section class="legacyAdminWrap">
      <div class="legacyHero">
        <div>
          <div class="legacyEyebrow">Compatibilità QR storici</div>
          <div class="h1">Pagine legacy</div>
          <div class="p">
            Queste pagine mantengono online i vecchi QR creati sul precedente qrfacile.it.
            Restano gratuite e accessibili senza login.
          </div>
        </div>

        <div class="legacyHeroBox">
          <span>Legacy attive</span>
          <b>{len(rows)}</b>
        </div>
      </div>

      <form method="get" action="/admin/legacy" class="card legacySearch">
        <div>
          <label>Cerca legacy</label>
          <input class="input" name="q" value="{esc(q)}" placeholder="cliente, vino, slug...">
        </div>

        <div class="legacySearchActions">
          <button class="btn btn-primary" type="submit">Cerca</button>
          <a class="btn" href="/admin/legacy">Reset</a>
        </div>
      </form>

      <div class="legacyList">
        {cards}
      </div>

      <div class="note" style="margin-top:18px">
        Regola operativa: le pagine legacy non consumano crediti, non richiedono piano e non vanno spente.
        I nuovi QR invece devono passare da registrazione, piano e crediti.
      </div>

      <style>
        .legacyAdminWrap {{
          max-width:1180px;
          margin:0 auto;
        }}

        .legacyHero {{
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

        .legacyEyebrow {{
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

        .legacyHeroBox {{
          border:1px solid rgba(2,8,23,.07);
          background:rgba(255,255,255,.72);
          border-radius:22px;
          padding:18px;
        }}

        .legacyHeroBox span {{
          display:block;
          color:#64748b;
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.07em;
        }}

        .legacyHeroBox b {{
          display:block;
          margin-top:8px;
          font-size:42px;
          line-height:1;
          font-weight:950;
        }}

        .legacySearch {{
          margin-top:18px;
          display:grid;
          grid-template-columns:minmax(0,1fr) auto;
          gap:14px;
          align-items:end;
        }}

        .legacySearchActions {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
        }}

        .legacyList {{
          display:grid;
          gap:12px;
          margin-top:18px;
        }}

        .legacyRow {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          background:rgba(255,255,255,.86);
          box-shadow:0 14px 45px rgba(2,8,23,.055);
          padding:16px;
          display:flex;
          justify-content:space-between;
          gap:16px;
          align-items:flex-start;
        }}

        .legacyTitle {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          align-items:center;
          font-size:17px;
          font-weight:950;
          color:#0f172a;
        }}

        .legacyMeta {{
          margin-top:7px;
          color:#64748b;
          font-size:13px;
          font-weight:800;
        }}

        .legacySource {{
          margin-top:6px;
          color:#64748b;
          font-size:12px;
          font-weight:720;
          word-break:break-word;
        }}

        .legacyActions {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          justify-content:flex-end;
        }}

        @media(max-width:820px) {{
          .legacyHero,
          .legacySearch {{
            grid-template-columns:1fr;
          }}

          .legacyRow {{
            flex-direction:column;
          }}

          .legacyActions {{
            justify-content:flex-start;
          }}
        }}

        @media(max-width:560px) {{
          .legacyActions .btn,
          .legacySearchActions .btn {{
            width:100%;
          }}
        }}
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Legacy",
        subtitle="Pagine legacy",
        body_html=body,
        actions_html=actions,
        user_email=user.get("email", ""),
        role="admin",
        credits=None,
    ))
