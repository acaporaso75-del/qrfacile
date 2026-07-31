# /opt/qrfacile/qrfacile_app/auth_routes.py
import time
import secrets
import os
import smtplib
import hashlib
import logging
from email.message import EmailMessage

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row
from passlib.hash import pbkdf2_sha256

from qrfacile_app.db import pg
from qrfacile_app.auth import COOKIE, SESSION_MAX_AGE_SECONDS
from qrfacile_app.ui_shell import page, top_actions, esc

router = APIRouter()
logger = logging.getLogger("qrfacile.auth_routes")

PASSWORD_RESET_TTL_SECONDS = 60 * 60
PASSWORD_RESET_NEUTRAL_MSG = "Se l’email è registrata, riceverai un link per reimpostare la password."  # pragma: allowlist secret



def now() -> int:
    return int(time.time())


def _create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (%s,%s,%s)",
                (token, int(user_id), now()),
            )
        conn.commit()
    return token


def _delete_session(token: str) -> None:
    if not token:
        return

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("DELETE FROM sessions WHERE token=%s", (token,))
        conn.commit()



def _clean_email(email: str) -> str:
    return "".join((email or "").split()).strip().lower()


def _base_url(request: Request) -> str:
    base = ""
    try:
        base = (getattr(request.app.state, "app_base_url", "") or "").rstrip("/")
    except Exception:
        base = ""

    if not base:
        host = request.headers.get("host", "")
        scheme = request.url.scheme
        if host:
            base = f"{scheme}://{host}".rstrip("/")

    return base


def _smtp_cfg():
    host = (os.getenv("SMTP_HOST", "") or "").strip()
    port = int((os.getenv("SMTP_PORT", "465") or "465").strip())
    user = (os.getenv("SMTP_USER", "") or "").strip()
    pwd = (os.getenv("SMTP_PASS", "") or "").strip()
    from_email = (
        (os.getenv("SMTP_FROM", "") or "").strip()
        or (os.getenv("FROM_EMAIL", "") or "").strip()
        or user
    )

    if not host or not user or not pwd or not from_email:
        return None

    return host, port, user, pwd, from_email


def _token_hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _send_password_reset_email(*, to_email: str, reset_link: str) -> tuple[bool, str]:
    cfg = _smtp_cfg()
    if not cfg:
        return False, "SMTP non configurato"

    host, port, user, pwd, from_email = cfg

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = "Recupero password QRFACILE"
    msg.set_content(
        f"""Buongiorno,

abbiamo ricevuto una richiesta di reimpostazione password per il tuo account QRFACILE.

Per scegliere una nuova password apri questo link entro 60 minuti:

{reset_link}

Se non hai richiesto tu il recupero password, ignora questa email.

QRFACILE
"""
    )

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=25) as s:
                s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=25) as s:
                s.starttls()
                s.login(user, pwd)
                s.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)


def _reset_request_ip(request: Request) -> str:
    try:
        return (request.client.host or "")[:80]
    except Exception:
        return ""


def _load_reset_token(cur, token: str) -> dict | None:
    token = (token or "").strip()
    if not token:
        return None

    cur.execute(
        """
        SELECT
          prt.id,
          prt.user_id,
          prt.expires_at,
          prt.used_at,
          u.email
        FROM password_reset_tokens prt
        JOIN users u ON u.id = prt.user_id
        WHERE prt.token_hash=%s
        LIMIT 1
        """,
        (_token_hash(token),),
    )
    return cur.fetchone()


def _reset_token_error(row: dict | None) -> str:
    if not row:
        return "Link di recupero non valido. Richiedi un nuovo link."
    if row.get("used_at"):
        return "Link di recupero già usato. Richiedi un nuovo link."
    if int(row.get("expires_at") or 0) < now():
        return "Link di recupero scaduto. Richiedi un nuovo link."
    return ""


def _forgot_password_body(msg: str = "", err: str = "") -> str:
    notice = f'<div class="note" style="margin-top:16px">{esc(msg)}</div>' if msg else ""
    error = f'<div class="note note-err" style="margin-top:16px">{esc(err)}</div>' if err else ""
    return f"""
    <section style="max-width:760px;margin:34px auto 0;padding:0 20px">
      <div class="card" style="padding:28px">
        <div class="h1">Recupero password</div>
        <div class="p" style="margin-top:10px;line-height:1.6">
          Inserisci l'email del tuo account QRFACILE. Se l'account esiste, riceverai un link valido per 60 minuti.
        </div>
        {notice}
        {error}
        <form method="post" action="/forgot-password" style="margin-top:22px;display:grid;gap:14px">
          <div>
            <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Email</label>
            <input class="input" name="email" type="email" required autocomplete="email" placeholder="nome@azienda.it"
              style="width:100%;font-size:16px;padding:15px 15px;border-radius:14px">
          </div>
          <button class="btn btn-primary" type="submit" style="width:100%;font-size:16px;padding:15px 18px;border-radius:16px">
            Invia link di recupero
          </button>
          <a class="btn" href="/login" style="text-align:center;border-radius:16px">Torna al login</a>
        </form>
      </div>
    </section>
    """


def _reset_password_body(token: str, err: str = "") -> str:
    error = f'<div class="note note-err" style="margin-top:16px">{esc(err)}</div>' if err else ""
    return f"""
    <section style="max-width:760px;margin:34px auto 0;padding:0 20px">
      <div class="card" style="padding:28px">
        <div class="h1">Reimposta password</div>
        <div class="p" style="margin-top:10px;line-height:1.6">
          Scegli una nuova password per il tuo account QRFACILE.
        </div>
        {error}
        <form method="post" action="/reset-password" style="margin-top:22px;display:grid;gap:14px">
          <input type="hidden" name="token" value="{esc(token)}">
          <div>
            <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Nuova password</label>
            <input class="input" name="password" type="password" required minlength="8" autocomplete="new-password"
              placeholder="Almeno 8 caratteri" style="width:100%;font-size:16px;padding:15px 15px;border-radius:14px">
          </div>
          <div>
            <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">Conferma password</label>
            <input class="input" name="password_confirm" type="password" required minlength="8" autocomplete="new-password"
              placeholder="Ripeti la password" style="width:100%;font-size:16px;padding:15px 15px;border-radius:14px">
          </div>
          <button class="btn btn-primary" type="submit" style="width:100%;font-size:16px;padding:15px 18px;border-radius:16px">
            Salva nuova password
          </button>
          <a class="btn" href="/login" style="text-align:center;border-radius:16px">Torna al login</a>
        </form>
      </div>
    </section>
    """


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_get(request: Request, msg: str = "", err: str = ""):
    actions = top_actions(
        ("/", "Home"),
        ("/login", "Login"),
        ("/support", "Supporto"),
    )
    return HTMLResponse(page(
        title="QRFACILE · Recupero password",
        subtitle="Recupero password",
        body_html=_forgot_password_body(msg=msg, err=err),
        actions_html=actions,
        msg="",
        err="",
    ))


@router.post("/forgot-password")
def forgot_password_post(request: Request, email: str = Form(...)):
    email = _clean_email(email)

    if email and "@" in email and "." in email:
        try:
            with pg() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        "SELECT id, email FROM users WHERE lower(email)=lower(%s) LIMIT 1",
                        (email,),
                    )
                    u = cur.fetchone()

                    if u:
                        raw_token = secrets.token_urlsafe(32)
                        ts = now()
                        exp = ts + PASSWORD_RESET_TTL_SECONDS
                        request_ip = _reset_request_ip(request)
                        cur.execute(
                            """
                            INSERT INTO password_reset_tokens
                              (user_id, token_hash, created_at, expires_at, request_ip)
                            VALUES
                              (%s,%s,%s,%s,%s)
                            """,
                            (int(u["id"]), _token_hash(raw_token), ts, exp, request_ip or None),
                        )
                        conn.commit()

                        reset_link = f"{_base_url(request)}/reset-password?token={raw_token}"
                        sent, smtp_error = _send_password_reset_email(
                            to_email=u.get("email") or email,
                            reset_link=reset_link,
                        )
                        if not sent:
                            logger.warning(
                                "Password reset email not sent for user_id=%s: %s",
                                int(u["id"]),
                                (smtp_error or "")[:180],
                            )
                    else:
                        conn.commit()
        except Exception as e:
            logger.warning("Password reset request failed: %s", str(e)[:180])

    return forgot_password_get(request, msg=PASSWORD_RESET_NEUTRAL_MSG)


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_get(request: Request, token: str = ""):
    token = (token or "").strip()
    actions = top_actions(
        ("/", "Home"),
        ("/login", "Login"),
        ("/forgot-password", "Richiedi nuovo link"),
    )

    row = None
    err = ""
    try:
        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                row = _load_reset_token(cur, token)
        err = _reset_token_error(row)
    except Exception as e:
        logger.warning("Password reset token validation failed: %s", str(e)[:180])
        err = "Link di recupero non valido. Richiedi un nuovo link."

    if err:
        body = f"""
        <section style="max-width:760px;margin:34px auto 0;padding:0 20px">
          <div class="card" style="padding:28px">
            <div class="h1">Link non valido</div>
            <div class="note note-err" style="margin-top:16px">{esc(err)}</div>
            <div class="row" style="margin-top:18px;gap:10px;flex-wrap:wrap">
              <a class="btn btn-primary" href="/forgot-password">Richiedi nuovo link</a>
              <a class="btn" href="/login">Torna al login</a>
            </div>
          </div>
        </section>
        """
    else:
        body = _reset_password_body(token)

    return HTMLResponse(page(
        title="QRFACILE · Reimposta password",
        subtitle="Reimposta password",
        body_html=body,
        actions_html=actions,
        msg="",
        err="",
    ))


@router.post("/reset-password")
def reset_password_post(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(""),
):
    token = (token or "").strip()
    password = password or ""
    password_confirm = password_confirm or ""

    if len(password) < 8:
        return HTMLResponse(page(
            title="QRFACILE · Reimposta password",
            subtitle="Reimposta password",
            body_html=_reset_password_body(token, err="Password minimo 8 caratteri."),
            actions_html=top_actions(("/login", "Login"), ("/forgot-password", "Richiedi nuovo link")),
            msg="",
            err="",
        ))

    if password_confirm and password != password_confirm:
        return HTMLResponse(page(
            title="QRFACILE · Reimposta password",
            subtitle="Reimposta password",
            body_html=_reset_password_body(token, err="Le password non coincidono."),
            actions_html=top_actions(("/login", "Login"), ("/forgot-password", "Richiedi nuovo link")),
            msg="",
            err="",
        ))

    try:
        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                row = _load_reset_token(cur, token)
                err = _reset_token_error(row)
                if err:
                    conn.rollback()
                    return RedirectResponse("/forgot-password?err=Link%20non%20valido%20o%20scaduto", status_code=303)

                user_id = int(row["user_id"])
                pass_hash = pbkdf2_sha256.hash(password)
                ts = now()

                cur.execute(
                    "UPDATE users SET pass_hash=%s WHERE id=%s",
                    (pass_hash, user_id),
                )
                cur.execute(
                    """
                    UPDATE password_reset_tokens
                    SET used_at=%s
                    WHERE user_id=%s
                      AND used_at IS NULL
                    """,
                    (ts, user_id),
                )
                cur.execute("DELETE FROM sessions WHERE user_id=%s", (user_id,))
                conn.commit()
    except Exception as e:
        logger.warning("Password reset update failed: %s", str(e)[:180])
        return RedirectResponse("/forgot-password?err=Impossibile%20reimpostare%20la%20password", status_code=303)

    return RedirectResponse("/login?reset=1", status_code=303)


@router.get("/login", response_class=HTMLResponse)
def login_get(request: Request, expired: str = "", created: str = "", reset: str = "", err: str = "", next: str = ""):
    msg = ""

    if expired == "1":
        msg = "Sessione scaduta, effettua di nuovo l’accesso."
    elif created == "1":
        msg = "Registrazione completata. Ora puoi accedere."
    elif reset == "1":
        msg = "Password aggiornata. Ora puoi accedere."

    actions = top_actions(
        ("/", "Home"),
        ("/pricing", "Prezzi"),
        ("/register-winery", "Registrati come Cantina"),
        ("/register-studio", "Registrati come Studio Grafico"),
    )

    body = """
    <section style="max-width:1120px;margin:34px auto 0;padding:0 28px">
      <div class="card" style="
        padding:0;
        overflow:hidden;
        border:1px solid rgba(2,8,23,.08);
        box-shadow:0 24px 80px rgba(2,8,23,.10);
        background:linear-gradient(135deg,rgba(255,255,255,.96),rgba(248,252,250,.92));
      ">
        <div class="login-grid" style="
          display:grid;
          grid-template-columns:1.1fr .9fr;
          gap:0;
          align-items:stretch;
        ">

          <div style="padding:42px 42px 38px">
            <div style="text-align:left">
              <div class="h1" style="margin:0;font-size:36px;letter-spacing:-.8px">
                Accedi a QRFACILE
              </div>

              <div class="p" style="font-size:16px;margin-top:12px;line-height:1.6">
                Gestisci etichette digitali vino, QR code, lotti, crediti ed esportazioni
                in modo semplice, ordinato e aggiornabile.
              </div>
            </div>

            <form method="post" action="/login" style="margin-top:28px">
              <input type="hidden" name="next" value="{esc(next)}">
              <div style="display:grid;gap:14px">
                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">
                    Email
                  </label>
                  <input class="input" name="email" type="email" required
                    placeholder="nome@azienda.it" autocomplete="email"
                    style="width:100%;font-size:16px;padding:15px 15px;border-radius:14px">
                </div>

                <div>
                  <label style="display:block;margin-bottom:7px;font-weight:700;color:#334155">
                    Password
                  </label>
                  <input class="input" name="password" type="password" required
                    placeholder="••••••••" autocomplete="current-password"
                    style="width:100%;font-size:16px;padding:15px 15px;border-radius:14px">
                  <div style="margin-top:8px;text-align:right">
                    <a href="/forgot-password" style="font-size:13px;font-weight:800;color:#0f766e;text-decoration:none">Password dimenticata?</a>
                  </div>
                </div>
              </div>

              <div style="margin-top:22px;display:grid;gap:11px">
                <button class="btn btn-primary" type="submit" style="
                  width:100%;
                  font-size:17px;
                  padding:16px 20px;
                  border-radius:16px;
                  font-weight:800;
                  box-shadow:0 14px 35px rgba(20,184,166,.20);
                ">
                  Entra
                </button>

                <a class="btn" href="/" style="
                  width:100%;
                  font-size:15px;
                  padding:14px 18px;
                  border-radius:16px;
                  text-align:center;
                ">
                  Torna alla home
                </a>
              </div>
            </form>

            <div class="card" style="
              margin-top:26px;
              background:rgba(255,255,255,.76);
              border:1px solid rgba(2,8,23,.07);
              box-shadow:none;
            ">
              <div class="h2" style="font-size:19px;margin:0">
                Non hai ancora un account?
              </div>

              <div class="p" style="margin-top:8px;line-height:1.55">
                Crea il tuo account e inizia a generare etichette digitali vino in pochi minuti.
              </div>

              <div class="login-register-grid" style="
                margin-top:17px;
                display:grid;
                grid-template-columns:1fr 1fr;
                gap:12px;
              ">
                <a class="btn btn-primary" href="/register-winery" style="
                  border-radius:999px;
                  text-align:center;
                  white-space:nowrap;
                  padding-left:14px;
                  padding-right:14px;
                ">
                  Registrati come Cantina
                </a>

                <a class="btn" href="/register-studio" style="
                  border-radius:999px;
                  text-align:center;
                  white-space:nowrap;
                  padding-left:14px;
                  padding-right:14px;
                ">
                  Registrati come Studio Grafico
                </a>
              </div>
            </div>
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
                Label Solution
              </div>

              <div class="h2" style="font-size:28px;margin-top:10px;line-height:1.15">
                QR professionali per cantine e studi grafici.
              </div>

              <div class="p" style="margin-top:12px;line-height:1.65">
                Un ambiente unico per creare, aggiornare e gestire le informazioni digitali
                collegate alle etichette vino.
              </div>

              <div style="display:grid;gap:12px;margin-top:22px">
                <div class="note" style="margin:0;background:rgba(255,255,255,.70)">
                  <b>Gestione lotti</b><br>
                  Dati sempre ordinati e aggiornabili.
                </div>

                <div class="note" style="margin:0;background:rgba(255,255,255,.70)">
                  <b>QR code export</b><br>
                  File pronti per grafica, stampa e archivio.
                </div>

                <div class="note" style="margin:0;background:rgba(255,255,255,.70)">
                  <b>Cantina + studio</b><br>
                  Percorsi separati e collaborazione più chiara.
                </div>
              </div>
            </div>
          </aside>
        </div>
      </div>

      <style>
        @media (max-width: 860px) {
          section {
            padding:0 16px !important;
          }

          .login-grid {
            grid-template-columns: 1fr !important;
          }

          .login-grid aside {
            border-left:0 !important;
            border-top:1px solid rgba(2,8,23,.06) !important;
            padding:28px !important;
          }

          .login-grid > div {
            padding:30px 22px !important;
          }

          .login-register-grid {
            grid-template-columns: 1fr !important;
          }
        }

        @media (max-width: 520px) {
          .login-register-grid a {
            white-space:normal !important;
          }
        }
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Login",
        subtitle="Login",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
    ))


@router.post("/login")
def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form(""),
):
    email = (email or "").strip().lower()
    password = password or ""

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, email, pass_hash, role FROM users WHERE lower(email)=lower(%s) LIMIT 1",
                (email,),
            )
            u = cur.fetchone()

    if not u:
        return login_get(request, err="Credenziali non valide", next=next)

    try:
        ok = pbkdf2_sha256.verify(password, u["pass_hash"])
    except Exception:
        ok = False

    if not ok:
        return login_get(request, err="Credenziali non valide", next=next)

    token = _create_session(int(u["id"]))

    next_url = (next or "").strip()

    # Sicurezza: accetta solo percorsi interni, niente redirect esterni.
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/app/start"

    resp = RedirectResponse(next_url, status_code=303)
    resp.set_cookie(
        key=COOKIE,
        value=token,
        httponly=True,
        max_age=SESSION_MAX_AGE_SECONDS,
        samesite="lax",
        path="/",
    )
    return resp


@router.get("/logout")
def logout(request: Request):
    token = (request.cookies.get(COOKIE) or "").strip()
    _delete_session(token)

    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE, path="/")
    return resp
