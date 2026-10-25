import time
from urllib.parse import quote_plus

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row
from passlib.hash import pbkdf2_sha256

from qrfacile_app.db import pg
from qrfacile_app.legal_core import record_registration_acceptances
from qrfacile_app.password_policy import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, new_password_error
from qrfacile_app.services.email_verification import create_verification
from qrfacile_app.ui_shell import page, top_actions, esc

router = APIRouter()


def now_epoch() -> int:
    return int(time.time())



def _studio_invite_get(cur, token: str) -> dict | None:
    token = (token or "").strip()
    if not token:
        return None

    cur.execute(
        """
        SELECT si.*, w.name AS winery_name
        FROM studio_invites si
        JOIN wineries w ON w.id = si.winery_id
        WHERE si.token=%s
        LIMIT 1
        """,
        (token,),
    )
    return cur.fetchone()


def _studio_invite_error(inv: dict | None, email: str) -> str:
    if not inv:
        return "Invito non trovato"
    if inv.get("used_at"):
        return "Invito già usato"
    if int(inv.get("expires_at") or 0) < now_epoch():
        return "Invito scaduto"
    if not inv.get("winery_id"):
        return "Invito non valido"

    invited_email = (inv.get("studio_email") or "").strip().lower()
    if email and invited_email and invited_email != (email or "").strip().lower():
        return "Invito riservato a un altro indirizzo email"

    return ""


def _accept_studio_invite(cur, inv: dict, studio_user_id: int, ts: int):
    winery_id = int(inv["winery_id"])

    cur.execute(
        """
        INSERT INTO studio_clients
          (studio_user_id, winery_id, can_view, can_edit, can_create, created_at)
        VALUES
          (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (studio_user_id, winery_id)
        DO UPDATE SET
          can_view=EXCLUDED.can_view,
          can_edit=EXCLUDED.can_edit,
          can_create=EXCLUDED.can_create
        """,
        (
            int(studio_user_id),
            winery_id,
            bool(inv.get("can_view")),
            bool(inv.get("can_edit")),
            bool(inv.get("can_create")),
            ts,
        ),
    )

    cur.execute(
        """
        UPDATE studio_invites
        SET used_at=%s,
            used_by_user_id=%s
        WHERE token=%s
        """,
        (ts, int(studio_user_id), inv["token"]),
    )


def _invite_next_after_login(inv: dict | None) -> str:
    if not inv:
        return "/studio"
    if inv.get("source_label_id"):
        return f"/app/label/{int(inv['source_label_id'])}"
    if inv.get("source_wine_id"):
        return f"/app/wine/{int(inv['source_wine_id'])}"
    return "/studio"

def _input(name: str, type_: str, placeholder: str, value: str = "", required: bool = False) -> str:
    req = "required" if required else ""
    labels = {
        "email": "Email di accesso",
        "password": "Password",  # pragma: allowlist secret
        "password_confirm": "Conferma password",  # pragma: allowlist secret
        "company_name": "Ragione sociale",
        "vat": "Partita IVA",
        "sdi": "Codice SDI",
        "pec": "PEC",
        "contact_name": "Nome del referente",
        "contact_phone": "Telefono del referente",
        "billing_address": "Indirizzo di fatturazione",
        "billing_city": "Città di fatturazione",
        "billing_cap": "CAP di fatturazione",
        "billing_province": "Provincia di fatturazione",
    }
    autocompletes = {
        "email": "email",
        "password": "new-password",  # pragma: allowlist secret
        "password_confirm": "new-password",  # pragma: allowlist secret
        "company_name": "organization",
        "pec": "email",
        "contact_name": "name",
        "contact_phone": "tel",
        "billing_address": "street-address",
        "billing_city": "address-level2",
        "billing_cap": "postal-code",
        "billing_province": "address-level1",
    }
    autocomplete = autocompletes.get(name, "off")

    return f"""
<input class="input" id="{esc(name)}" name="{esc(name)}" type="{esc(type_)}" value="{esc(value)}"
  aria-label="{esc(labels.get(name, name.replace('_', ' ').title()))}"
  autocomplete="{esc(autocomplete)}" placeholder="{esc(placeholder)}" {req}{f' minlength="{MIN_PASSWORD_LENGTH}" maxlength="{MAX_PASSWORD_LENGTH}"' if type_ == 'password' else ''}
  style="width:100%;font-size:15px;padding:14px 15px;border-radius:14px">
""".strip()


@router.get("/register-studio", response_class=HTMLResponse)
def register_studio_get(err: str = "", msg: str = "", invite: str = "", next: str = ""):
    actions = top_actions(
        ("/", "Home"),
        ("/login", "Login"),
        ("/register-winery", "Registrati come Cantina"),
    )

    invite = (invite or "").strip()
    invite_note = ""
    if invite:
        try:
            with pg() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    inv = _studio_invite_get(cur, invite)
                    emsg = _studio_invite_error(inv, "")
                    if inv and not emsg:
                        invite_note = f"""
                        <div class="note" style="margin-top:16px;background:rgba(255,255,255,.72)">
                          <b>Invito cantina rilevato</b><br>
                          Cantina: <b>{esc(inv.get('winery_name') or '-')}</b><br>
                          Completa la registrazione con l’email invitata: <b>{esc(inv.get('studio_email') or '-')}</b>.
                        </div>
                        """
                    elif emsg:
                        invite_note = f"<div class='note note-err' style='margin-top:16px'>{esc(emsg)}</div>"
        except Exception:
            invite_note = "<div class='note note-err' style='margin-top:16px'>Errore nel controllo invito.</div>"

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
                background:rgba(59,130,246,.10);
                color:#1d4ed8;
                font-size:12px;
                font-weight:900;
                letter-spacing:.08em;
                text-transform:uppercase;
              ">
                Account Studio Grafico
              </div>

              <fieldset style="margin-top:20px;padding:16px;border:1px solid rgba(15,23,42,.14);border-radius:14px">
                <legend style="font-weight:800;padding:0 6px">Condizioni e privacy</legend>
                <label style="display:flex;gap:10px;align-items:flex-start;line-height:1.45">
                  <input type="checkbox" name="terms_accepted" value="yes" required style="margin-top:4px">
                  <span>Ho letto e accetto i <a href="/terms" target="_blank" rel="noopener">Termini di servizio</a> (versione 25/10/2026).</span>
                </label>
                <label style="display:flex;gap:10px;align-items:flex-start;line-height:1.45;margin-top:10px">
                  <input type="checkbox" name="privacy_acknowledged" value="yes" required style="margin-top:4px">
                  <span>Dichiaro di aver letto l’<a href="/privacy" target="_blank" rel="noopener">informativa privacy</a> (versione 25/10/2026). Non è un consenso marketing.</span>
                </label>
              </fieldset>

              <div class="h1" style="margin-top:14px;font-size:36px;letter-spacing:-.8px">
                Registrazione Studio
              </div>

              <div class="p" style="font-size:16px;margin-top:10px;line-height:1.6">
                Crea il profilo dello studio grafico per collaborare con le cantine,
                gestire clienti, inviti, permessi e QR dinamici.
              </div>
            </div>

            {invite_note}

            <form method="post" action="/register-studio" style="margin-top:26px">
              <input type="hidden" name="invite" value="{esc(invite)}">
              <input type="hidden" name="next" value="{esc(next if next.startswith('/') and not next.startswith('//') else '')}">
              <div class="grid2 register-form-grid">
                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Email login</label>
                  {_input("email", "email", "nome@studio.it", "", True)}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Password (min {MIN_PASSWORD_LENGTH})</label>
                  {_input("password", "password", "••••••••", "", True)}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Conferma password</label>
                  {_input("password_confirm", "password", "Ripeti la password", "", True)}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Ragione sociale</label>
                  {_input("company_name", "text", "Studio XYZ Srl", "", True)}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Partita IVA</label>
                  {_input("vat", "text", "IT12345678901", "", True)}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">SDI</label>
                  {_input("sdi", "text", "XXXXXXX", "", True)}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">PEC opzionale</label>
                  {_input("pec", "text", "pec@studiopec.it")}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Referente</label>
                  {_input("contact_name", "text", "Nome Cognome", "", True)}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Cellulare referente</label>
                  {_input("contact_phone", "text", "+39 333 1234567", "", True)}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Indirizzo fatturazione opzionale</label>
                  {_input("billing_address", "text", "Via..., n°")}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Città opzionale</label>
                  {_input("billing_city", "text", "Benevento")}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">CAP opzionale</label>
                  {_input("billing_cap", "text", "82100")}
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Provincia opzionale</label>
                  {_input("billing_province", "text", "BN")}
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
                  Crea account Studio
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
                I dati fiscali saranno usati per fatturazione e gestione operativa.
              </div>
            </form>
          </div>

          <aside style="
            padding:42px;
            background:
              radial-gradient(circle at 20% 20%, rgba(191,219,254,.58), transparent 34%),
              radial-gradient(circle at 80% 35%, rgba(167,243,208,.48), transparent 38%),
              linear-gradient(135deg,rgba(239,246,255,.92),rgba(236,253,245,.92));
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
                color:#1d4ed8;
              ">
                Per studi grafici
              </div>

              <div class="h2" style="font-size:28px;margin-top:10px;line-height:1.15">
                Collabora con le cantine in modo più ordinato.
              </div>

              <div class="p" style="margin-top:12px;line-height:1.65">
                Lo studio può gestire clienti, inviti e permessi, mantenendo separati
                ruoli e responsabilità operative.
              </div>

              <div style="display:grid;gap:12px;margin-top:22px">
                <div class="note" style="margin:0;background:rgba(255,255,255,.70)">
                  <b>Inviti cantina</b><br>
                  Collega nuovi clienti con permessi chiari e gestione multi-cliente.
                </div>

                <div class="note" style="margin:0;background:rgba(255,255,255,.70)">
                  <b>Permessi operativi</b><br>
                  Visualizzazione, modifica e creazione gestite.
                </div>

                <div class="note" style="margin:0;background:rgba(255,255,255,.70)">
                  <b>Export QR</b><br>
                  File QR pronti per grafica, stampa e consegna.
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
        title="QRFACILE · Registrazione Studio",
        subtitle="Registrazione Studio",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
    ))


@router.post("/register-studio")
def register_studio_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    company_name: str = Form(...),
    vat: str = Form(...),
    sdi: str = Form(...),
    pec: str = Form(""),
    contact_name: str = Form(...),
    contact_phone: str = Form(...),
    billing_address: str = Form(""),
    billing_city: str = Form(""),
    billing_cap: str = Form(""),
    billing_province: str = Form(""),
    terms_accepted: str = Form(""),
    privacy_acknowledged: str = Form(""),
    invite: str = Form(""),
    next: str = Form(""),
):
    email = (email or "").strip().lower()
    password = password or ""

    if "@" not in email:
        return RedirectResponse("/register-studio?err=Email%20non%20valida", status_code=303)

    policy_error = new_password_error(password)
    if policy_error:
        return RedirectResponse(f"/register-studio?err={quote_plus(policy_error)}", status_code=303)

    if password != (password_confirm or ""):
        return RedirectResponse("/register-studio?err=Le%20password%20non%20coincidono", status_code=303)

    if terms_accepted != "yes" or privacy_acknowledged != "yes":
        return RedirectResponse(
            "/register-studio?err=Devi%20accettare%20i%20Termini%20e%20confermare%20la%20Privacy",
            status_code=303,
        )

    company_name = (company_name or "").strip()
    vat = (vat or "").strip()
    sdi = (sdi or "").strip()
    pec = (pec or "").strip() or None
    contact_name = (contact_name or "").strip()
    contact_phone = (contact_phone or "").strip()

    billing_address = (billing_address or "").strip() or None
    billing_city = (billing_city or "").strip() or None
    billing_cap = (billing_cap or "").strip() or None
    billing_province = (billing_province or "").strip() or None
    invite = (invite or "").strip()
    invite_qs = f"&invite={invite}" if invite else ""

    if not company_name or not vat or not sdi or not contact_name or not contact_phone:
        return RedirectResponse(
            f"/register-studio?err=Compila%20tutti%20i%20campi%20obbligatori{invite_qs}",
            status_code=303,
        )

    ts = now_epoch()
    pass_hash = pbkdf2_sha256.hash(password)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id FROM users WHERE lower(email)=lower(%s) LIMIT 1",
                (email,),
            )

            if cur.fetchone():
                return RedirectResponse(
                    f"/register-studio?err=Email%20gia%20registrata{invite_qs}",
                    status_code=303,
                )

            inv = None
            if invite:
                inv = _studio_invite_get(cur, invite)
                emsg = _studio_invite_error(inv, email)
                if emsg:
                    return RedirectResponse(
                        f"/register-studio?err={emsg.replace(' ', '%20')}&invite={invite}",
                        status_code=303,
                    )

            cur.execute(
                """
                INSERT INTO users(
                  email, pass_hash, role, created_at, email_verified,
                  email_verification_required, last_qr_type, pref_lock_qr_type
                )
                VALUES (%s,%s,'studio',%s,0,TRUE,'modulare',0)
                RETURNING id
                """,
                (email, pass_hash, ts),
            )
            user_id = int(cur.fetchone()["id"])

            cur.execute(
                """
                INSERT INTO studios(
                    user_id, company_name, vat, sdi, pec, contact_name, contact_phone,
                    billing_address, billing_city, billing_cap, billing_province, billing_country, created_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'IT',%s)
                """,
                (
                    user_id,
                    company_name,
                    vat,
                    sdi,
                    pec,
                    contact_name,
                    contact_phone,
                    billing_address,
                    billing_city,
                    billing_cap,
                    billing_province,
                    ts,
                ),
            )

            if inv:
                _accept_studio_invite(cur, inv, user_id, ts)

            record_registration_acceptances(cur, user_id=user_id, request=request)

        conn.commit()

    try:
        base_url = str(getattr(request.app.state, "app_base_url", "") or "").rstrip("/")
        if not base_url:
            base_url = f"{request.url.scheme}://{request.headers.get('host', '')}".rstrip("/")
        create_verification(user_id=user_id, base_url=base_url)
    except Exception:
        # Account remains restricted and can retry from /verify-email-required.
        pass

    if invite:
        return RedirectResponse(f"/login?created=1&next={_invite_next_after_login(inv)}", status_code=303)

    if next.startswith("/") and not next.startswith("//"):
        return RedirectResponse(f"/login?created=1&next={next}", status_code=303)

    return RedirectResponse("/login?created=1", status_code=303)
