import time

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row
from passlib.hash import pbkdf2_sha256

from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, esc

router = APIRouter()


def now() -> int:
    return int(time.time())


def _hash_pw(pw: str) -> str:
    return pbkdf2_sha256.hash(pw or "")


def _invite_get(cur, token: str) -> dict | None:
    token = (token or "").strip()
    if not token:
        return None

    cur.execute(
        """
        SELECT
               si.token,
               si.winery_id,
               si.inviter_user_id,
               si.studio_email,
               si.can_view,
               si.can_edit,
               si.can_create,
               si.created_at,
               si.expires_at,
               si.used_at,
               si.used_by_user_id,
               COALESCE(si.recommended_pack, '') AS recommended_pack,
               COALESCE(st.company_name, '') AS inviter_company_name,
               COALESCE(u.email, '') AS inviter_email
        FROM studio_invites si
        LEFT JOIN users u ON u.id = si.inviter_user_id
        LEFT JOIN studios st ON st.user_id = si.inviter_user_id
        WHERE si.token=%s
        LIMIT 1
        """,
        (token,),
    )
    return cur.fetchone()


def _invite_is_valid(inv: dict) -> tuple[bool, str]:
    if not inv:
        return False, "Invito non trovato"

    if inv.get("used_at"):
        return False, "Invito già usato"

    exp = int(inv.get("expires_at") or 0)
    if exp and exp < now():
        return False, "Invito scaduto"

    if not inv.get("inviter_user_id"):
        return False, "Invito non valido (studio mancante)"

    return True, ""


def _input(name: str, type_: str, placeholder: str, value: str = "", required: bool = False) -> str:
    req = "required" if required else ""

    return f"""
<input class="input" name="{esc(name)}" type="{esc(type_)}" value="{esc(value)}"
  placeholder="{esc(placeholder)}" {req}
  style="width:100%;font-size:15px;padding:14px 15px;border-radius:14px">
""".strip()


@router.get("/register-winery", response_class=HTMLResponse)
def register_winery_get(request: Request, invite: str = "", err: str = "", msg: str = ""):
    invite = (invite or "").strip()

    actions = top_actions(
        ("/", "Home"),
        ("/login", "Login"),
        ("/register-studio", "Registrati come Studio Grafico"),
    )

    inv_note = ""
    if invite:
        try:
            with pg() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    inv = _invite_get(cur, invite)
                    ok, emsg = _invite_is_valid(inv)

                    if ok:
                        invited_email = (inv.get("studio_email") or "").strip() or "-"
                        inviter_company = (inv.get("inviter_company_name") or "").strip()
                        inviter_email = (inv.get("inviter_email") or "").strip()

                        if inviter_company and inviter_email:
                            inviter_label = f"{inviter_company} · {inviter_email}"
                        elif inviter_company:
                            inviter_label = inviter_company
                        elif inviter_email:
                            inviter_label = inviter_email
                        else:
                            inviter_label = "Studio grafico"

                        perms = []
                        if inv.get("can_view"):
                            perms.append("view")
                        if inv.get("can_edit"):
                            perms.append("edit")
                        if inv.get("can_create"):
                            perms.append("create")

                        perms_txt = ", ".join(perms) if perms else "-"

                        pack_labels = {
                            "start": "Start · 20 crediti · €29",
                            "pro": "Cantina · 60 crediti · €79",
                            "plus": "Business · 200 crediti · €199",
                            "unlimited": "Non disponibile online",
                        }
                        recommended_pack = (inv.get("recommended_pack") or "").strip().lower()
                        recommended_txt = pack_labels.get(recommended_pack, "")

                        recommended_html = ""
                        if recommended_txt:
                            recommended_html = f"<br>Piano consigliato: <b>{esc(recommended_txt)}</b>"

                        inv_note = f"""
                        <div class="note" style="margin-top:16px;background:rgba(255,255,255,.72)">
                          <b>Invito Studio rilevato</b><br>
                          Studio invitante: <b>{esc(inviter_label)}</b><br>
                          Email cantina invitata: <b>{esc(invited_email)}</b><br>
                          Permessi: <span class="mono">{esc(perms_txt)}</span>{recommended_html}
                        </div>
                        """
                    else:
                        inv_note = f"""
                        <div class="note note-err" style="margin-top:16px">
                          <b>Invito:</b> {esc(emsg)}
                        </div>
                        """

        except Exception:
            inv_note = """
            <div class="note note-err" style="margin-top:16px">
              Errore nel controllo invito. Puoi comunque registrarti.
            </div>
            """

    body = f"""
    <section style="max-width:1120px;margin:34px auto 0;padding:0 28px">
      <div class="card" style="
        padding:0;
        overflow:hidden;
        border:1px solid rgba(2,8,23,.08);
        box-shadow:0 24px 80px rgba(2,8,23,.10);
        background:linear-gradient(135deg,rgba(255,255,255,.96),rgba(248,252,250,.92));
      ">
        <div class="register-grid" style="
          display:grid;
          grid-template-columns:1.18fr .82fr;
          gap:0;
          align-items:stretch;
        ">

          <div style="padding:42px 42px 38px">
            <div>
              <div style="
                display:inline-flex;
                align-items:center;
                gap:8px;
                padding:7px 12px;
                border-radius:999px;
                background:rgba(20,184,166,.10);
                color:#0f766e;
                font-size:12px;
                font-weight:900;
                letter-spacing:.08em;
                text-transform:uppercase;
              ">
                Account Cantina
              </div>

              <div class="h1" style="margin-top:14px;font-size:36px;letter-spacing:-.8px">
                Registrazione Cantina
              </div>

              <div class="p" style="font-size:16px;margin-top:10px;line-height:1.6">
                Crea l’account della cantina per gestire lotti, etichette digitali,
                QR dinamici, dati fiscali ed esportazioni.
              </div>
            </div>

            {inv_note}

            <form method="post" action="/register-winery" style="margin-top:26px">
              <input type="hidden" name="invite" value="{esc(invite)}">

              <div class="grid2 register-form-grid">
                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Email</label>
                  {_input("email", "email", "nome@cantina.it", "", True)}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Password (min 8)</label>
                  {_input("password", "password", "••••••••", "", True)}
                </div>
              </div>

              <div style="margin-top:14px">
                <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Nome Cantina</label>
                {_input("name", "text", "Cantina XYZ", "", True)}
              </div>

              <div class="grid2 register-form-grid" style="margin-top:14px">
                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">P.IVA</label>
                  {_input("vat", "text", "IT12345678901", "", True)}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">SDI</label>
                  {_input("sdi", "text", "XXXXXXX", "", True)}
                </div>
              </div>

              <div class="grid2 register-form-grid" style="margin-top:14px">
                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">PEC opzionale</label>
                  {_input("pec", "text", "pec@cantinapec.it")}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Telefono opzionale</label>
                  {_input("phone", "text", "+39 0824 ...")}
                </div>
              </div>

              <div class="grid2 register-form-grid" style="margin-top:14px">
                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Referente</label>
                  {_input("contact_name", "text", "Nome Cognome", "", True)}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Cellulare referente</label>
                  {_input("contact_phone", "text", "+39 333 ...", "", True)}
                </div>
              </div>

              <div class="grid2 register-form-grid" style="margin-top:14px">
                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Città opzionale</label>
                  {_input("city", "text", "Benevento")}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Provincia opzionale</label>
                  {_input("province", "text", "BN")}
                </div>
              </div>

              <div class="register-actions" style="
                margin-top:22px;
                display:grid;
                grid-template-columns:1fr 1fr;
                gap:12px;
              ">
                <button class="btn btn-primary" type="submit" style="
                  border-radius:16px;
                  font-size:16px;
                  padding:15px 18px;
                  font-weight:800;
                ">
                  Crea account Cantina
                </button>

                <a class="btn" href="/login" style="
                  border-radius:16px;
                  text-align:center;
                  font-size:16px;
                  padding:15px 18px;
                ">
                  Ho già un account
                </a>
              </div>

              <div class="note" style="margin-top:16px;background:rgba(255,255,255,.72)">
                Dopo la registrazione potrai creare lotti, caricare immagini, compilare compliance
                ed esportare il QR per la stampa.
              </div>
            </form>
          </div>

          <aside style="
            padding:42px;
            background:
              radial-gradient(circle at 20% 20%, rgba(167,243,208,.55), transparent 34%),
              radial-gradient(circle at 80% 35%, rgba(191,219,254,.58), transparent 38%),
              linear-gradient(135deg,rgba(236,253,245,.92),rgba(239,246,255,.92));
            border-left:1px solid rgba(2,8,23,.06);
            display:flex;
            flex-direction:column;
            justify-content:center;
          ">
            <div style="
              background:rgba(255,255,255,.72);
              border:1px solid rgba(2,8,23,.08);
              border-radius:26px;
              padding:28px;
              box-shadow:0 24px 60px rgba(2,8,23,.08);
            ">
              <div style="
                font-size:13px;
                font-weight:900;
                letter-spacing:.12em;
                text-transform:uppercase;
                color:#0f766e;
              ">
                Per le cantine
              </div>

              <div class="h2" style="font-size:28px;margin-top:10px;line-height:1.15">
                Etichette digitali vino sempre aggiornabili.
              </div>

              <div class="p" style="margin-top:12px;line-height:1.65">
                Una dashboard semplice per creare lotti, gestire dati obbligatori
                e generare QR dinamici professionali.
              </div>

              <div style="display:grid;gap:12px;margin-top:22px">
                <div class="note" style="margin:0;background:rgba(255,255,255,.70)">
                  <b>QR dinamico per il vino</b><br>
                  Informazioni digitali collegate al lotto.
                </div>

                <div class="note" style="margin:0;background:rgba(255,255,255,.70)">
                  <b>Dati aggiornabili</b><br>
                  Modifica e consultazione semplice.
                </div>

                <div class="note" style="margin:0;background:rgba(255,255,255,.70)">
                  <b>Export stampa</b><br>
                  File QR pronti per grafica, tipografia e archivio.
                </div>
              </div>
            </div>
          </aside>
        </div>
      </div>

      <style>
        @media (max-width: 900px) {{
          section {{
            padding:0 16px !important;
          }}

          .register-grid {{
            grid-template-columns:1fr !important;
          }}

          .register-grid aside {{
            border-left:0 !important;
            border-top:1px solid rgba(2,8,23,.06) !important;
            padding:28px !important;
          }}

          .register-grid > div {{
            padding:30px 22px !important;
          }}

          .register-form-grid,
          .register-actions {{
            grid-template-columns:1fr !important;
          }}
        }}
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Registrazione Cantina",
        subtitle="Registrazione Cantina",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
    ))


@router.post("/register-winery")
def register_winery_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    name: str = Form(...),
    vat: str = Form(...),
    sdi: str = Form(...),
    pec: str = Form(""),
    phone: str = Form(""),
    contact_name: str = Form(...),
    contact_phone: str = Form(...),
    city: str = Form(""),
    province: str = Form(""),
    invite: str = Form(""),
):
    email = (email or "").strip().lower()
    password = password or ""

    if "@" not in email:
        return RedirectResponse("/register-winery?err=Email%20non%20valida", status_code=303)

    if len(password) < 8:
        return RedirectResponse("/register-winery?err=Password%20minimo%208%20caratteri", status_code=303)

    invite = (invite or "").strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            inv = None
            if invite:
                inv = _invite_get(cur, invite)
                ok, msg = _invite_is_valid(inv)

                if not ok:
                    return RedirectResponse(
                        f"/register-winery?invite={invite}&err={msg.replace(' ', '%20')}",
                        status_code=303,
                    )

            try:
                cur.execute(
                    """
                    INSERT INTO users (email, pass_hash, role, created_at, email_verified)
                    VALUES (%s,%s,'winery',%s,1)
                    RETURNING id
                    """,
                    (email, _hash_pw(password), now()),
                )
                user_id = int(cur.fetchone()["id"])

            except Exception:
                conn.rollback()
                return RedirectResponse(
                    f"/register-winery?invite={invite}&err=Email%20gia%20registrata",
                    status_code=303,
                )

            cur.execute(
                """
                INSERT INTO wineries (owner_user_id, name, vat, sdi, pec, phone, city, province, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    user_id,
                    (name or "").strip(),
                    (vat or "").strip(),
                    (sdi or "").strip(),
                    (pec or "").strip(),
                    (phone or "").strip(),
                    (city or "").strip(),
                    (province or "").strip(),
                    now(),
                ),
            )
            winery_id = int(cur.fetchone()["id"])

            # Crediti gratuiti iniziali QRFACILE:
            # 3 crediti wine = 3 QR vino da 10 anni oppure 1 QR da 25 anni + 1 QR da 10 anni.
            cur.execute(
                """
                INSERT INTO credit_ledger
                  (user_id, credit_type, delta, reason, ref_table, ref_id, created_at)
                VALUES
                  (%s, 'wine', 3, 'seed', 'users', %s, %s)
                """,
                (user_id, user_id, now()),
            )

            if inv:
                studio_user_id = int(inv["inviter_user_id"])

                cur.execute(
                    """
                    INSERT INTO studio_clients (studio_user_id, winery_id, can_view, can_edit, can_create, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        studio_user_id,
                        winery_id,
                        bool(inv.get("can_view")),
                        bool(inv.get("can_edit")),
                        bool(inv.get("can_create")),
                        now(),
                    ),
                )

                cur.execute(
                    """
                    UPDATE studio_invites
                    SET used_at=%s,
                        used_by_user_id=%s,
                        winery_id=%s
                    WHERE token=%s
                    """,
                    (now(), user_id, winery_id, inv["token"]),
                )

            conn.commit()

    return RedirectResponse("/login?created=1", status_code=303)
