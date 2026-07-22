# /opt/qrfacile/qrfacile_app/start_ui.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, esc
from qrfacile_app.ui_layout import pill

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


def _tile(
    mode: str,
    title: str,
    desc: str,
    icon: str,
    tag: str = "",
    cta: str = "",
    credit_label: str = "",
    credit_value: int | None = None,
    disabled: bool = False,
) -> str:
    tag_html = ""
    if tag:
        tag_color = "#0f766e"
        tag_bg = "rgba(20,184,166,.10)"
        if "beta" in tag.lower():
            tag_color = "#1d4ed8"
            tag_bg = "rgba(59,130,246,.10)"
        if "arrivo" in tag.lower():
            tag_color = "#64748b"
            tag_bg = "rgba(100,116,139,.10)"

        tag_html = f"""
        <div style="
          display:inline-flex;
          align-items:center;
          width:max-content;
          padding:5px 9px;
          border-radius:999px;
          background:{tag_bg};
          color:{tag_color};
          font-size:11px;
          font-weight:900;
          letter-spacing:.06em;
          text-transform:uppercase;
          margin-bottom:10px;
        ">
          {esc(tag)}
        </div>
        """

    credit_html = ""
    if credit_label and credit_value is not None:
        credit_html = f"""
          <div style="
            margin-top:14px;
            display:inline-flex;
            align-items:center;
            gap:8px;
            padding:8px 10px;
            border-radius:12px;
            background:rgba(248,250,252,.92);
            border:1px solid rgba(2,8,23,.07);
            color:#334155;
            font-size:13px;
            font-weight:850;
          ">
            <span>{esc(credit_label)}</span>
            <b style="font-size:16px;color:#0f172a">{int(credit_value)}</b>
          </div>
        """

    cta_html = ""
    if cta:
        cta_html = f"""
          <div style="
            margin-top:16px;
            display:inline-flex;
            align-items:center;
            justify-content:center;
            width:max-content;
            max-width:100%;
            padding:10px 13px;
            border-radius:14px;
            background:{'rgba(148,163,184,.12)' if disabled else 'rgba(15,118,110,.10)'};
            color:{'#64748b' if disabled else '#0f766e'};
            font-size:13px;
            font-weight:900;
          ">
            {esc(cta)}
          </div>
        """

    button_attrs = 'disabled aria-disabled="true"' if disabled else f'name="mode" value="{esc(mode)}"'
    button_type = "button" if disabled else "submit"
    cursor = "not-allowed" if disabled else "pointer"
    opacity = ".74" if disabled else "1"

    return f"""
    <button class="card start-tile" {button_attrs} type="{button_type}" style="
      text-align:left;
      cursor:{cursor};
      padding:22px;
      border:1px solid rgba(2,8,23,.08);
      background:linear-gradient(135deg,rgba(255,255,255,.96),rgba(248,252,250,.92));
      box-shadow:0 18px 45px rgba(2,8,23,.06);
      transition:transform .16s ease, box-shadow .16s ease, border-color .16s ease;
      opacity:{opacity};
    ">
      <div style="display:flex;gap:15px;align-items:flex-start">
        <div style="
          width:52px;
          height:52px;
          border-radius:18px;
          display:flex;
          align-items:center;
          justify-content:center;
          background:
            radial-gradient(circle at 20% 20%, rgba(167,243,208,.70), transparent 45%),
            linear-gradient(135deg,rgba(236,253,245,.95),rgba(239,246,255,.95));
          font-size:24px;
          border:1px solid rgba(2,8,23,.07);
          flex:0 0 auto;
        ">
          {esc(icon)}
        </div>

        <div style="flex:1;min-width:0">
          {tag_html}
          <div class="h2" style="font-size:21px;line-height:1.18;margin:0">
            {esc(title)}
          </div>
          <div class="p" style="margin-top:9px;line-height:1.55">
            {esc(desc)}
          </div>
          {credit_html}
          {cta_html}
        </div>
      </div>
    </button>
    """


@router.get("/app/start", response_class=HTMLResponse)
def start(request: Request, msg: str = "", err: str = ""):
    u = require_any_role(request, ("winery", "studio", "admin"))
    role = (u.get("role") or "").strip().lower()
    uid = int(u["id"])

    balances = {"wine": 0, "generic": 0}

    try:
        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                balances = _balances(cur, uid)
    except Exception:
        pass

    actions = ""
    actions += pill(f"wine: {balances.get('wine', 0)}", "green")
    actions += " "
    actions += pill(f"generic: {balances.get('generic', 0)}")
    actions += " "
    actions += top_actions(
        ("/app/billing", "Crediti"),
        ("/app/dashboard", "Dashboard"),
        ("/logout", "Logout"),
    )

    tiles = []

    tiles.append(_tile(
        "dashboard",
        "Wine Compliance",
        "Modulo per etichette digitali vino, compliance, lotti, immagini, pubblicazione ed export QR per la stampa. 10 anni = 1 credito · 25 anni = 2 crediti.",
        "📋",
        "Attivo",
        "Dashboard Wine",
        "Crediti wine",
        int(balances.get("wine", 0)),
    ))

    tiles.append(_tile(
        "qr_link",
        "QR Link Diretto",
        "Modulo tecnico per configurare QR dinamici verso link esterni aggiornabili. Primi 3 QR link gratuiti · dal 4° = 1 credito generic.",
        "🔗",
        "Beta tecnica",
        "Configura QR Link",
        "Crediti generic",
        int(balances.get("generic", 0)),
    ))

    tiles.append(_tile(
        "vcard",
        "vCard / Biglietto digitale",
        "Modulo per contatti digitali, biglietti da visita e profili aggiornabili collegati a QR.",
        "👤",
        "In arrivo",
        "In arrivo",
        disabled=True,
    ))

    tiles.append(_tile(
        "menu",
        "Menu",
        "Modulo per menu digitali aggiornabili, liste prodotti, carte stagionali e consultazione rapida.",
        "🍽️",
        "In arrivo",
        "In arrivo",
        disabled=True,
    ))

    tiles.append(_tile(
        "quiz",
        "Quiz/Formazione",
        "Modulo per percorsi formativi, quiz, raccolta risposte e contenuti didattici via QR.",
        "🎓",
        "In arrivo",
        "In arrivo",
        disabled=True,
    ))

    tiles.append(_tile(
        "warehouse",
        "Magazzino",
        "Modulo per schede operative, prodotti, scaffali, materiali e inventari leggeri.",
        "📦",
        "In arrivo",
        "In arrivo",
        disabled=True,
    ))

    profile_tiles = []

    if role == "studio":
        profile_tiles.append(_tile(
            "studio_area",
            "Area Studio",
            "Invita cantine, gestisci clienti collegati e accedi al lavoro operativo dello studio grafico.",
            "🎨",
            "studio",
        ))

        profile_tiles.append(_tile(
            "studio_comm",
            "Bonus e commissioni",
            "Riepilogo bonus maturando, clienti collegati e richieste payout.",
            "💶",
            "studio",
        ))

    if role == "admin":
        profile_tiles.append(_tile(
            "admin_stats",
            "Statistiche admin",
            "Console admin con KPI, ricerca cantine e contesto operativo attivo.",
            "📊",
            "admin",
        ))

        profile_tiles.append(_tile(
            "admin_payouts",
            "Admin · Payout",
            "Approva e gestisci i payout richiesti dagli studi grafici.",
            "🛠️",
            "admin",
        ))

    profile_tools_html = ""
    if profile_tiles:
        profile_tools_html = f"""
          <div class="profile-tools" style="
            margin-top:30px;
            padding-top:24px;
            border-top:1px solid rgba(2,8,23,.08);
          ">
            <div class="h2" style="font-size:22px;margin:0">
              Strumenti del tuo profilo
            </div>

            <div class="p" style="margin-top:7px;max-width:760px;line-height:1.55">
              Accessi operativi dedicati al tuo ruolo.
            </div>

            <div class="profile-tools-grid" style="
              display:grid;
              grid-template-columns:repeat(2,minmax(0,1fr));
              gap:16px;
              margin-top:16px;
            ">
              {''.join(profile_tiles)}
            </div>
          </div>
        """

    role_label = {
        "winery": "Cantina",
        "studio": "Studio grafico",
        "admin": "Amministratore",
    }.get(role, role or "-")

    body = f"""
    <section style="max-width:1180px;margin:0 auto">
      <div class="card" style="
        padding:0;
        overflow:hidden;
        border:1px solid rgba(2,8,23,.08);
        box-shadow:0 24px 80px rgba(2,8,23,.08);
        background:linear-gradient(135deg,rgba(255,255,255,.97),rgba(248,252,250,.94));
      ">
        <div style="
          padding:34px 36px;
          background:
            radial-gradient(circle at 8% 15%, rgba(167,243,208,.50), transparent 28%),
            radial-gradient(circle at 92% 12%, rgba(191,219,254,.50), transparent 30%),
            linear-gradient(135deg,rgba(236,253,245,.82),rgba(239,246,255,.78));
          border-bottom:1px solid rgba(2,8,23,.07);
        ">
          <div style="
            display:flex;
            align-items:flex-start;
            justify-content:space-between;
            gap:20px;
            flex-wrap:wrap;
          ">
            <div>
              <div style="
                display:inline-flex;
                align-items:center;
                gap:8px;
                padding:7px 12px;
                border-radius:999px;
                background:rgba(255,255,255,.70);
                color:#0f766e;
                font-size:12px;
                font-weight:900;
                letter-spacing:.08em;
                text-transform:uppercase;
                border:1px solid rgba(2,8,23,.06);
              ">
                Area operativa · {esc(role_label)}
              </div>

              <div class="h1" style="
                margin-top:14px;
                font-size:38px;
                letter-spacing:-.9px;
                line-height:1.08;
              ">
                Centro Moduli QRFACILE
              </div>

              <div class="p" style="
                margin-top:10px;
                max-width:760px;
                font-size:16px;
                line-height:1.65;
              ">
                scegli il modulo da utilizzare.
              </div>
            </div>

            <div style="
              min-width:220px;
              background:rgba(255,255,255,.72);
              border:1px solid rgba(2,8,23,.07);
              border-radius:22px;
              padding:18px;
              box-shadow:0 18px 45px rgba(2,8,23,.06);
            ">
              <div style="font-size:12px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:#64748b">
                Crediti disponibili
              </div>

              <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px">
                <div style="
                  padding:12px;
                  border-radius:16px;
                  background:rgba(236,253,245,.90);
                  border:1px solid rgba(20,184,166,.14);
                ">
                  <div style="font-size:12px;color:#0f766e;font-weight:800">wine</div>
                  <div style="font-size:26px;font-weight:900;line-height:1">
                    {int(balances.get('wine', 0))}
                  </div>
                </div>

                <div style="
                  padding:12px;
                  border-radius:16px;
                  background:rgba(239,246,255,.90);
                  border:1px solid rgba(59,130,246,.14);
                ">
                  <div style="font-size:12px;color:#1d4ed8;font-weight:800">generic</div>
                  <div style="font-size:26px;font-weight:900;line-height:1">
                    {int(balances.get('generic', 0))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <form method="post" action="/app/start/select" style="padding:30px 36px 34px">
          <div class="start-grid" style="
            display:grid;
            grid-template-columns:repeat(2,minmax(0,1fr));
            gap:16px;
          ">
            {''.join(tiles)}
          </div>

          {profile_tools_html}

          <div class="note" style="
            margin-top:18px;
            background:rgba(255,255,255,.72);
            border:1px solid rgba(2,8,23,.07);
          ">
            <b>Suggerimento:</b> se non hai crediti disponibili, entra nella sezione <b>Crediti</b>.
          </div>
        </form>
      </div>

      <style>
        .start-tile:not(:disabled):hover {{
          transform:translateY(-2px);
          box-shadow:0 26px 65px rgba(2,8,23,.10) !important;
          border-color:rgba(20,184,166,.22) !important;
        }}

        .start-tile:disabled {{
          color:inherit;
        }}

        @media (max-width: 980px) {{
          .start-grid {{
            grid-template-columns:1fr !important;
          }}

          .profile-tools-grid {{
            grid-template-columns:1fr !important;
          }}
        }}

        @media (max-width: 640px) {{
          section {{
            padding:0 4px !important;
          }}
        }}
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Centro Moduli",
        subtitle="scegli il modulo da utilizzare",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=u.get("email", ""),
        role=role,
        credits=balances,
    ))


@router.get("/app/menu")
def menu_alias():
    return RedirectResponse("/app/start", status_code=303)


@router.post("/app/start/select")
def select_mode(request: Request, mode: str = Form(...)):
    u = require_any_role(request, ("winery", "studio", "admin"))
    role = (u.get("role") or "").strip().lower()
    mode = (mode or "").strip().lower()

    if mode in ("admin_stats", "admin_payouts") and role != "admin":
        return RedirectResponse("/app/start?err=Accesso%20admin%20richiesto", status_code=303)

    if mode == "dashboard":
        return RedirectResponse("/app/dashboard", status_code=303)

    if mode == "new_wine":
        return RedirectResponse("/app/new-wine", status_code=303)

    if mode == "qr_link":
        return RedirectResponse("/app/new-external", status_code=303)

    if mode == "studio_area":
        return RedirectResponse("/studio", status_code=303)

    if mode == "studio_comm":
        return RedirectResponse("/studio/commissions", status_code=303)

    if mode == "admin_stats":
        return RedirectResponse("/admin", status_code=303)

    if mode == "admin_payouts":
        return RedirectResponse("/admin/payouts", status_code=303)

    return RedirectResponse("/app/dashboard", status_code=303)
