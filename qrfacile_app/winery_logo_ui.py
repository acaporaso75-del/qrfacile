# /opt/qrfacile/qrfacile_app/winery_logo_ui.py
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.media import process_logo
from qrfacile_app.ui_shell import page, top_actions, pill, esc

router = APIRouter()


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


def _admin_active_winery_id(cur, user_id: int) -> int | None:
    cur.execute(
        "SELECT admin_active_winery_id FROM users WHERE id=%s LIMIT 1",
        (int(user_id),),
    )
    r = cur.fetchone() or {}
    wid = r.get("admin_active_winery_id")
    return int(wid) if wid else None


def _resolve_winery(cur, user: dict) -> dict:
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    if role == "admin":
        wid = _admin_active_winery_id(cur, uid)

        if not wid:
            raise HTTPException(403, "Admin senza cantina attiva")

        cur.execute(
            """
            SELECT id, name, logo_path
            FROM wineries
            WHERE id=%s
            LIMIT 1
            """,
            (int(wid),),
        )
        w = cur.fetchone()

        if not w:
            raise HTTPException(404, "Cantina non trovata")

        return w

    if role == "winery":
        cur.execute(
            """
            SELECT id, name, logo_path
            FROM wineries
            WHERE owner_user_id=%s
            LIMIT 1
            """,
            (uid,),
        )
        w = cur.fetchone()

        if not w:
            raise HTTPException(404, "Cantina non trovata")

        return w

    raise HTTPException(403, "Solo cantina o admin possono gestire il logo")


@router.get("/app/winery/logo", response_class=HTMLResponse)
def winery_logo_page(request: Request, msg: str = "", err: str = ""):
    user = require_any_role(request, ("winery", "admin"))
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            balances = _balances(cur, uid)
            winery = _resolve_winery(cur, user)

    logo_path = (winery.get("logo_path") or "").strip()

    logo_html = """
    <div class="logoPreviewEmpty">
      <div>🏷️</div>
      <b>Nessun logo caricato</b>
      <span>Carica il logo della cantina per mostrarlo nella pagina pubblica del QR.</span>
    </div>
    """

    if logo_path:
        src = logo_path if logo_path.startswith("/") else f"/uploads/{logo_path.lstrip('/')}"
        logo_html = f"""
        <div class="logoPreviewBox">
          <img src="{esc(src)}" alt="Logo cantina">
        </div>
        <div class="logoPath">
          <span>File attuale</span>
          <b>{esc(logo_path)}</b>
        </div>
        """

    actions = (
        pill(f"wine: {balances.get('wine', 0)}", "green") + " " +
        pill(f"generic: {balances.get('generic', 0)}") + " " +
        top_actions(
            ("/app/dashboard", "Dashboard"),
            ("/app/start", "Menu"),
            ("/logout", "Logout"),
        )
    )

    body = f"""
    <section class="logoWrap">
      <div class="logoHero">
        <div>
          <div class="logoEyebrow">Identità cantina</div>
          <div class="h1">Logo cantina</div>
          <div class="p">
            Carica o aggiorna il logo di <b>{esc(winery.get("name") or "Cantina")}</b>.
            Il logo verrà mostrato nella pagina pubblica del QR vino, in modo sobrio e professionale.
          </div>
        </div>

        <div class="logoHeroBox">
          <span>Cantina</span>
          <b>{esc(winery.get("name") or "-")}</b>
        </div>
      </div>

      <div class="logoGrid">
        <div class="card logoPanel">
          <div class="logoPanelHead">
            <div>
              <div class="logoSmallLabel">Logo attuale</div>
              <div class="h2">Anteprima</div>
            </div>
            <span class="logoIcon">🖼️</span>
          </div>

          {logo_html}
        </div>

        <div class="card logoPanel">
          <div class="logoPanelHead">
            <div>
              <div class="logoSmallLabel">Upload</div>
              <div class="h2">Carica logo</div>
            </div>
            <span class="logoIcon">⬆️</span>
          </div>

          <form method="post"
                action="/app/winery/logo"
                enctype="multipart/form-data"
                class="logoUploadForm">
            <div>
              <label>File logo</label>
              <input class="input" type="file" name="logo" accept="image/png,image/jpeg,image/webp" required>
            </div>

            <button class="btn btn-primary" type="submit">Salva logo</button>
          </form>

          <div class="note" style="margin-top:14px">
            Consigliato: logo PNG con sfondo trasparente o immagine ad alta qualità.
            Il sistema ottimizza il file per l’uso web.
          </div>
        </div>
      </div>

      <div class="card logoPanel" style="margin-top:18px">
        <div class="h2">Dove comparirà</div>
        <div class="p">
          Il logo comparirà nella pagina pubblica del QR vino, sopra il nome del prodotto.
          Non viene usato per fini pubblicitari: serve solo a identificare correttamente la cantina/produttore.
        </div>

        <div style="margin-top:16px;display:flex;gap:10px;flex-wrap:wrap">
          <a class="btn" href="/app/dashboard">Torna alla dashboard</a>
          <a class="btn" href="/demo/public-label" target="_blank">Vedi esempio pagina QR</a>
        </div>
      </div>

      <style>
        .logoWrap {{
          max-width:1180px;
          margin:0 auto;
        }}

        .logoHero {{
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
          grid-template-columns:minmax(0,1fr) 260px;
          gap:24px;
          align-items:end;
        }}

        .logoEyebrow {{
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

        .logoHeroBox {{
          border:1px solid rgba(2,8,23,.07);
          background:rgba(255,255,255,.72);
          border-radius:22px;
          padding:18px;
        }}

        .logoHeroBox span {{
          display:block;
          font-size:12px;
          color:#64748b;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.07em;
        }}

        .logoHeroBox b {{
          display:block;
          margin-top:8px;
          font-size:20px;
          line-height:1.15;
          font-weight:950;
        }}

        .logoGrid {{
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:18px;
          margin-top:18px;
        }}

        .logoPanel {{
          padding:22px;
        }}

        .logoPanelHead {{
          display:flex;
          justify-content:space-between;
          gap:14px;
          align-items:flex-start;
          margin-bottom:16px;
        }}

        .logoSmallLabel {{
          color:#64748b;
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.08em;
        }}

        .logoIcon {{
          width:40px;
          height:40px;
          border-radius:16px;
          display:inline-flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.88),rgba(207,232,255,.80));
          border:1px solid rgba(2,8,23,.07);
          font-size:19px;
          flex:0 0 auto;
        }}

        .logoPreviewBox {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:24px;
          background:#fff;
          padding:28px;
          min-height:240px;
          display:flex;
          align-items:center;
          justify-content:center;
        }}

        .logoPreviewBox img {{
          max-width:100%;
          max-height:180px;
          object-fit:contain;
          display:block;
        }}

        .logoPreviewEmpty {{
          min-height:240px;
          border:1px dashed rgba(2,8,23,.16);
          border-radius:24px;
          background:
            radial-gradient(circle at 20% 10%, rgba(191,245,230,.45), transparent 50%),
            rgba(255,255,255,.70);
          display:flex;
          align-items:center;
          justify-content:center;
          flex-direction:column;
          text-align:center;
          padding:24px;
        }}

        .logoPreviewEmpty div {{
          width:58px;
          height:58px;
          border-radius:20px;
          display:flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.85),rgba(207,232,255,.85));
          font-size:26px;
          margin-bottom:12px;
        }}

        .logoPreviewEmpty b {{
          font-size:17px;
          font-weight:950;
        }}

        .logoPreviewEmpty span {{
          color:#64748b;
          font-size:13px;
          font-weight:750;
          margin-top:5px;
          line-height:1.45;
        }}

        .logoPath {{
          margin-top:14px;
          border:1px solid rgba(2,8,23,.07);
          background:rgba(255,255,255,.70);
          border-radius:18px;
          padding:12px;
        }}

        .logoPath span {{
          display:block;
          color:#64748b;
          font-size:11px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.06em;
        }}

        .logoPath b {{
          display:block;
          margin-top:5px;
          font-size:12px;
          word-break:break-word;
        }}

        .logoUploadForm {{
          display:grid;
          grid-template-columns:minmax(0,1fr) auto;
          gap:12px;
          align-items:end;
        }}

        @media(max-width:980px) {{
          .logoHero,
          .logoGrid {{
            grid-template-columns:1fr;
          }}
        }}

        @media(max-width:560px) {{
          .logoHero,
          .logoPanel {{
            padding:22px;
          }}

          .logoUploadForm {{
            grid-template-columns:1fr;
          }}

          .logoUploadForm .btn {{
            width:100%;
          }}
        }}
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Logo cantina",
        subtitle="Identità cantina",
        body_html=body,
        actions_html=actions,
        role=role,
        user_email=user.get("email", ""),
        credits=balances,
        msg=msg,
        err=err,
    ))


@router.post("/app/winery/logo")
def winery_logo_upload(request: Request, logo: UploadFile = File(...)):
    user = require_any_role(request, ("winery", "admin"))

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            winery = _resolve_winery(cur, user)
            winery_id = int(winery["id"])

    try:
        paths = process_logo(logo, winery_id)
        logo_path = paths.get("logo_path") or ""
    except Exception:
        return RedirectResponse(
            "/app/winery/logo?err=Logo%20non%20valido%20o%20errore%20upload",
            status_code=303,
        )

    if not logo_path:
        return RedirectResponse(
            "/app/winery/logo?err=Logo%20non%20salvato",
            status_code=303,
        )

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE wineries
                SET logo_path=%s
                WHERE id=%s
                """,
                (logo_path, winery_id),
            )
            conn.commit()

    return RedirectResponse(
        "/app/winery/logo?msg=Logo%20cantina%20aggiornato",
        status_code=303,
    )
