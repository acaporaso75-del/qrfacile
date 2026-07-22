import os
import time
import secrets
import smtplib
from email.message import EmailMessage
from urllib.parse import quote_plus

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role, get_current_user
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, esc, pill

router = APIRouter()

INVITE_TTL_DAYS = 14


def now_epoch() -> int:
    return int(time.time())


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))
    except Exception:
        return "-"


def _clean_email(email: str) -> str:
    return "".join((email or "").split()).strip().lower()


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


def _send_studio_invite_email(
    *,
    to_email: str,
    invite_link: str,
    winery_name: str,
) -> tuple[bool, str]:
    cfg = _smtp_cfg()
    if not cfg:
        return False, "SMTP non configurato"

    host, port, user, pwd, from_email = cfg

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = f"Invito QRFACILE – Accesso studio per {winery_name}"

    msg.set_content(
        f"""Buongiorno,

la cantina "{winery_name}" ti ha invitato su QRFACILE come studio grafico.

QRFACILE permette a cantina e studio grafico di lavorare in modo ordinato su:
- etichette digitali vino
- QR code
- immagini
- dati obbligatori
- export per la stampa

Per accettare l'invito, accedi o registrati come STUDIO GRAFICO e apri questo link:

{invite_link}

Se non hai richiesto questo invito, puoi ignorare questa email.

QRFACILE
Il QR del vino, fatto semplice.
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


def _get_winery_for_user(cur, user: dict) -> dict:
    role = (user.get("role") or "").lower().strip()

    if role == "admin":
        # Admin: usa contesto cantina attivo, se esiste
        try:
            cur.execute("SELECT admin_active_winery_id FROM users WHERE id=%s LIMIT 1", (int(user["id"]),))
            r = cur.fetchone() or {}
            wid = r.get("admin_active_winery_id")
            if wid:
                cur.execute("SELECT * FROM wineries WHERE id=%s LIMIT 1", (int(wid),))
                w = cur.fetchone()
                if w:
                    return w
        except Exception:
            pass
        raise HTTPException(400, "Admin: seleziona prima una cantina da /admin")

    if role != "winery":
        raise HTTPException(403, "Pagina riservata alla cantina")

    cur.execute("SELECT * FROM wineries WHERE owner_user_id=%s LIMIT 1", (int(user["id"]),))
    w = cur.fetchone()
    if not w:
        raise HTTPException(404, "Cantina non trovata per questo utente")
    return w


def _columns(cur, table: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    return {r["column_name"] for r in (cur.fetchall() or [])}


def _invite_redirect_target(inv: dict | None) -> str:
    if not inv:
        return "/studio?msg=Invito%20accettato"
    label_id = inv.get("source_label_id")
    wine_id = inv.get("source_wine_id")
    if label_id:
        return f"/app/label/{int(label_id)}?msg=Invito%20accettato"
    if wine_id:
        return f"/app/wine/{int(wine_id)}?msg=Invito%20accettato"
    return "/studio?msg=Invito%20accettato"


def _current_user_or_none(request: Request) -> dict | None:
    try:
        return get_current_user(request)
    except HTTPException as e:
        if int(getattr(e, "status_code", 0) or 0) == 303:
            return None
        raise


def _studio_invite_accept_url(token: str) -> str:
    return f"/app/invite/studio/accept/{esc((token or '').strip())}"


def _studio_invite_actions(token: str):
    token = (token or "").strip()
    accept_url = _studio_invite_accept_url(token)
    return top_actions(
        (f"/login?next={accept_url}", "Accedi e accetta invito"),
        (f"/register-studio?invite={esc(token)}", "Registrati come Studio"),
    )


def _studio_invite_public_page(
    *,
    token: str,
    inv: dict | None,
    heading: str,
    message: str,
    show_auth_ctas: bool = True,
    show_logout_cta: bool = False,
) -> HTMLResponse:
    token = (token or "").strip()
    accept_url = _studio_invite_accept_url(token)
    login_url = f"/login?next={accept_url}"
    register_url = f"/register-studio?invite={esc(token)}"

    studio_email = "-"
    winery_name = "-"
    expires_at = "-"
    perms_html = ""

    if inv:
        studio_email = inv.get("studio_email") or "-"
        winery_name = inv.get("winery_name") or "-"
        expires_at = _fmt_ts(int(inv.get("expires_at") or 0))
        perms_html = f"""
        <div class="row" style="margin-top:12px;gap:8px;flex-wrap:wrap">
          {pill("vista", "green" if inv.get("can_view") else "muted")}
          {pill("modifica", "green" if inv.get("can_edit") else "muted")}
          {pill("creazione", "green" if inv.get("can_create") else "muted")}
        </div>
        """

    ctas = ""
    if show_auth_ctas:
        ctas = f"""
        <div class="row" style="margin-top:18px;gap:10px;flex-wrap:wrap">
          <a class="btn btn-primary" href="{login_url}">Accedi e accetta invito</a>
          <a class="btn" href="{register_url}">Registrati come Studio</a>
        </div>
        """
    elif show_logout_cta:
        ctas = f"""
        <div class="row" style="margin-top:18px;gap:10px;flex-wrap:wrap">
          <a class="btn btn-primary" href="/logout">Esci e accedi come Studio</a>
          <a class="btn" href="{register_url}">Registrati come Studio</a>
        </div>
        """

    body = f"""
    <section style="max-width:920px;margin:22px auto 0">
      <div class="card" style="padding:24px">
        <div class="h1">Invito Studio QRFACILE</div>
        <div class="p" style="margin-top:10px;line-height:1.6">{esc(message)}</div>

        <div class="card" style="margin-top:18px;background:rgba(248,250,252,.78);box-shadow:none">
          <div class="h2">{esc(heading)}</div>
          <div class="p" style="margin-top:10px;line-height:1.7">
            Email invitata: <b>{esc(studio_email)}</b><br>
            Cantina che invita: <b>{esc(winery_name)}</b><br>
            Scadenza invito: <b>{esc(expires_at)}</b>
          </div>
          {perms_html}
          {ctas}
        </div>
      </div>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Invito Studio",
        subtitle="Invito Studio",
        body_html=body,
        actions_html=_studio_invite_actions(token),
    ))



def _current_user_or_none(request: Request) -> dict | None:
    try:
        return get_current_user(request)
    except HTTPException as e:
        if int(getattr(e, "status_code", 0) or 0) == 303:
            return None
        raise


def _studio_invite_accept_url(token: str) -> str:
    return f"/app/invite/studio/accept/{esc((token or '').strip())}"


def _studio_invite_actions(token: str):
    token = (token or "").strip()
    accept_url = _studio_invite_accept_url(token)
    return top_actions(
        (f"/login?next={accept_url}", "Accedi e accetta invito"),
        (f"/register-studio?invite={esc(token)}", "Registrati come Studio"),
    )


def _studio_invite_public_page(
    *,
    token: str,
    inv: dict | None,
    heading: str,
    message: str,
    show_auth_ctas: bool = True,
    show_logout_cta: bool = False,
) -> HTMLResponse:
    token = (token or "").strip()
    accept_url = _studio_invite_accept_url(token)
    login_url = f"/login?next={accept_url}"
    register_url = f"/register-studio?invite={esc(token)}"

    studio_email = "-"
    winery_name = "-"
    expires_at = "-"
    perms_html = ""

    if inv:
        studio_email = inv.get("studio_email") or "-"
        winery_name = inv.get("winery_name") or "-"
        expires_at = _fmt_ts(int(inv.get("expires_at") or 0))
        perms_html = f"""
        <div class="row" style="margin-top:12px;gap:8px;flex-wrap:wrap">
          {pill("vista", "green" if inv.get("can_view") else "muted")}
          {pill("modifica", "green" if inv.get("can_edit") else "muted")}
          {pill("creazione", "green" if inv.get("can_create") else "muted")}
        </div>
        """

    ctas = ""
    if show_auth_ctas:
        ctas = f"""
        <div class="row" style="margin-top:18px;gap:10px;flex-wrap:wrap">
          <a class="btn btn-primary" href="{login_url}">Accedi e accetta invito</a>
          <a class="btn" href="{register_url}">Registrati come Studio</a>
        </div>
        """
    elif show_logout_cta:
        ctas = f"""
        <div class="row" style="margin-top:18px;gap:10px;flex-wrap:wrap">
          <a class="btn btn-primary" href="/logout">Esci e accedi con l'account corretto</a>
          <a class="btn" href="{register_url}">Registrati come Studio</a>
        </div>
        """

    body = f"""
    <section style="max-width:920px;margin:22px auto 0">
      <div class="card" style="padding:24px">
        <div class="h1">Invito Studio QRFACILE</div>
        <div class="p" style="margin-top:10px;line-height:1.6">{esc(message)}</div>

        <div class="card" style="margin-top:18px;background:rgba(248,250,252,.78);box-shadow:none">
          <div class="h2">{esc(heading)}</div>
          <div class="p" style="margin-top:10px;line-height:1.7">
            Email invitata: <b>{esc(studio_email)}</b><br>
            Cantina che invita: <b>{esc(winery_name)}</b><br>
            Scadenza invito: <b>{esc(expires_at)}</b>
          </div>
          {perms_html}
          {ctas}
        </div>
      </div>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Invito Studio",
        subtitle="Invito Studio",
        body_html=body,
        actions_html=_studio_invite_actions(token),
    ))


def _studio_invite_email_error(inv: dict, user: dict) -> str:
    role = (user.get("role") or "").lower().strip()
    if role == "admin":
        return ""

    invited_email = (inv.get("studio_email") or "").strip().lower()
    user_email = (user.get("email") or "").strip().lower()
    if invited_email and invited_email != user_email:
        return (
            f"Questo invito è destinato a {invited_email}. "
            f"Stai usando {user_email or '-'}. "
            "Esci e accedi con l’account corretto."
        )

    return ""


def _accept_studio_invite_row(cur, inv: dict, studio_user_id: int, ts: int) -> None:
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



@router.get("/studio/settings", response_class=HTMLResponse)
def studio_settings_profile(request: Request, msg: str = "", err: str = ""):
    user = require_any_role(request, ("studio", "admin"))
    role = (user.get("role") or "").lower().strip()
    uid = int(user.get("id") or user.get("user_id") or 0)

    linked_wineries = 0
    pending_invites = 0

    if role == "studio":
        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int AS cnt
                    FROM studio_clients
                    WHERE studio_user_id=%s
                    """,
                    (uid,),
                )
                linked_wineries = int((cur.fetchone() or {}).get("cnt") or 0)

                cur.execute(
                    """
                    SELECT COUNT(*)::int AS cnt
                    FROM studio_invites
                    WHERE inviter_user_id=%s
                      AND used_at IS NULL
                      AND expires_at>%s
                    """,
                    (uid, int(time.time())),
                )
                pending_invites = int((cur.fetchone() or {}).get("cnt") or 0)

    actions = top_actions(
        ("/studio", "Area Studio"),
        ("/app/billing", "Crediti"),
        ("/app/start", "Menu"),
        ("/logout", "Logout"),
    )

    if role == "admin":
        body = """
        <section style="max-width:980px;margin:18px auto 0">
          <div class="card">
            <div class="h1">Profilo Studio</div>
            <div class="p" style="margin-top:10px">
              Come admin puoi accedere all’Area Studio, ma questa pagina mostra il profilo operativo
              solo quando l’utente autenticato è uno Studio Grafico.
            </div>
            <div class="row" style="margin-top:16px;gap:10px;flex-wrap:wrap">
              <a class="btn btn-primary" href="/studio">Vai ad Area Studio</a>
              <a class="btn" href="/admin">Console admin</a>
            </div>
          </div>
        </section>
        """
    else:
        email = esc(user.get("email") or "-")
        body = f"""
        <section style="max-width:980px;margin:18px auto 0">
          <div class="card">
            <div class="h1">Profilo Studio</div>
            <div class="p" style="margin-top:10px">
              Account Studio: <b>{email}</b>
            </div>

            <div class="row" style="margin-top:18px;gap:12px;flex-wrap:wrap">
              <div class="card" style="min-width:220px;box-shadow:none;background:rgba(248,250,252,.85)">
                <div class="muted">Cantine collegate</div>
                <div class="h1" style="margin-top:6px">{linked_wineries}</div>
              </div>

              <div class="card" style="min-width:220px;box-shadow:none;background:rgba(248,250,252,.85)">
                <div class="muted">Inviti in attesa</div>
                <div class="h1" style="margin-top:6px">{pending_invites}</div>
              </div>
            </div>

            <div class="note" style="margin-top:18px">
              Da questa sezione lo Studio può controllare il proprio profilo operativo.
              La gestione dei clienti, degli inviti e dei workspace avviene dall’Area Studio.
            </div>

            <div class="row" style="margin-top:16px;gap:10px;flex-wrap:wrap">
              <a class="btn btn-primary" href="/studio">Apri Area Studio</a>
              <a class="btn" href="/app/billing">Crediti e piani</a>
            </div>
          </div>
        </section>
        """

    return HTMLResponse(page(
        title="QRFACILE · Profilo Studio",
        subtitle="Profilo Studio",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=user.get("email", ""),
        role=role,
    ))



@router.get("/app/settings/studios")
def studios_settings_redirect(request: Request, msg: str = "", err: str = ""):
    suffix = ""
    params = []
    if msg:
        params.append(f"msg={quote_plus(msg)}")
    if err:
        params.append(f"err={quote_plus(err)}")
    if params:
        suffix = "?" + "&".join(params)
    return RedirectResponse(f"/app/winery/settings{suffix}", status_code=303)


@router.post("/app/settings/studios/invite")
def studios_invite_post(
    request: Request,
    studio_email: str = Form(...),
    preset: str = Form(""),
    can_view: str = Form(None),
    can_edit: str = Form(None),
    can_create: str = Form(None),
    source_wine_id: int = Form(0),
    source_label_id: int = Form(0),
):
    user = require_any_role(request, ("winery", "admin"))
    studio_email = _clean_email(studio_email)

    if not studio_email or "@" not in studio_email or "." not in studio_email:
        return RedirectResponse("/app/winery/settings?err=Email%20non%20valida", status_code=303)

    preset = (preset or "").strip().lower()
    if preset == "view":
        cv, ce, cc = True, False, False
    elif preset == "graphic":
        cv, ce, cc = True, True, False
    elif preset == "full":
        cv, ce, cc = True, True, True
    else:
        cv = bool(can_view)
        ce = bool(can_edit)
        cc = bool(can_create)

    token = secrets.token_urlsafe(24)
    ts = now_epoch()
    exp = ts + INVITE_TTL_DAYS * 86400

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _get_winery_for_user(cur, user)
            winery_id = int(w["id"])
            winery_name = w.get("name") or f"Cantina {winery_id}"

            cols = [
                "token",
                "winery_id",
                "inviter_user_id",
                "studio_email",
                "can_view",
                "can_edit",
                "can_create",
                "created_at",
                "expires_at",
            ]
            vals = [token, winery_id, int(user["id"]), studio_email, cv, ce, cc, ts, exp]
            invite_cols = _columns(cur, "studio_invites")
            if int(source_wine_id or 0) > 0 and "source_wine_id" in invite_cols:
                cols.append("source_wine_id")
                vals.append(int(source_wine_id))
            if int(source_label_id or 0) > 0 and "source_label_id" in invite_cols:
                cols.append("source_label_id")
                vals.append(int(source_label_id))

            placeholders = ",".join(["%s"] * len(vals))
            cur.execute(
                f"INSERT INTO studio_invites ({','.join(cols)}) VALUES ({placeholders})",
                tuple(vals),
            )
            conn.commit()

    invite_link = f"{_base_url(request)}/app/invite/studio/accept/{token}"

    sent, smtp_error = _send_studio_invite_email(
        to_email=studio_email,
        invite_link=invite_link,
        winery_name=winery_name,
    )

    if sent:
        msg = quote_plus("Invito creato ed email inviata allo studio")
        return RedirectResponse(f"/app/winery/settings?msg={msg}", status_code=303)

    msg = quote_plus("Invito creato. Email non inviata: copia il link dagli inviti recenti")
    if smtp_error:
        err = quote_plus(f"SMTP: {smtp_error[:160]}")
        return RedirectResponse(f"/app/winery/settings?msg={msg}&err={err}", status_code=303)

    return RedirectResponse(f"/app/winery/settings?msg={msg}", status_code=303)



@router.get("/app/invite/studio/accept/{token}", response_class=HTMLResponse)
def studio_accept_invite(request: Request, token: str):
    token = (token or "").strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
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
            inv = cur.fetchone()

    ts = now_epoch()
    if not inv:
        return _studio_invite_public_page(
            token=token,
            inv=None,
            heading="Invito non trovato",
            message="Il link non è valido oppure l'invito è stato rimosso.",
            show_auth_ctas=False,
        )

    if inv.get("used_at"):
        return _studio_invite_public_page(
            token=token,
            inv=inv,
            heading="Invito già usato",
            message="Questo invito è già stato accettato. Accedi allo Studio per continuare.",
            show_auth_ctas=True,
        )

    if ts > int(inv.get("expires_at") or 0):
        return _studio_invite_public_page(
            token=token,
            inv=inv,
            heading="Invito scaduto",
            message="Questo invito non è più valido. Chiedi alla cantina di inviare un nuovo invito.",
            show_auth_ctas=False,
        )

    if not inv.get("winery_id"):
        return _studio_invite_public_page(
            token=token,
            inv=inv,
            heading="Invito non valido",
            message="L'invito non contiene una cantina valida.",
            show_auth_ctas=False,
        )

    user = _current_user_or_none(request)
    if not user:
        return _studio_invite_public_page(
            token=token,
            inv=inv,
            heading="Accetta invito Studio",
            message="La cantina ti ha invitato a collaborare come Studio Grafico. Accedi se hai già un account, oppure registrati come Studio mantenendo questo invito.",
            show_auth_ctas=True,
        )

    role = (user.get("role") or "").lower().strip()
    if role not in ("studio", "admin"):
        return _studio_invite_public_page(
            token=token,
            inv=inv,
            heading="Questo invito è destinato a uno Studio Grafico",
            message="Sei già autenticato, ma non con un account Studio Grafico. Esci e accedi con l'account corretto per accettare l'invito.",
            show_auth_ctas=False,
            show_logout_cta=True,
        )

    email_error = _studio_invite_email_error(inv, user)
    if email_error:
        return _studio_invite_public_page(
            token=token,
            inv=inv,
            heading="Account non corretto per questo invito",
            message=email_error,
            show_auth_ctas=False,
            show_logout_cta=True,
        )

    studio_user_id = int(user["id"])

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            _accept_studio_invite_row(cur, inv, studio_user_id, ts)
            conn.commit()

    return RedirectResponse(_invite_redirect_target(inv), status_code=303)


@router.post("/app/invite/studio/accept/{token}")
def studio_accept_invite_post(request: Request, token: str):
    user = require_any_role(request, ("studio", "admin"))
    role = (user.get("role") or "").lower().strip()

    if role not in ("studio", "admin"):
        return _studio_invite_public_page(
            token=token,
            inv=None,
            heading="Questo invito è destinato a uno Studio Grafico",
            message="Esci e accedi con un account Studio Grafico per accettare l'invito.",
            show_auth_ctas=False,
            show_logout_cta=True,
        )

    ts = now_epoch()
    studio_user_id = int(user["id"])
    token = (token or "").strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
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
            inv = cur.fetchone()

            if not inv:
                return _studio_invite_public_page(
                    token=token,
                    inv=None,
                    heading="Invito non trovato",
                    message="Il link non è valido oppure l'invito è stato rimosso.",
                    show_auth_ctas=False,
                )
            if inv.get("used_at"):
                return _studio_invite_public_page(
                    token=token,
                    inv=inv,
                    heading="Invito già usato",
                    message="Questo invito è già stato accettato.",
                    show_auth_ctas=True,
                )
            if ts > int(inv["expires_at"]):
                return _studio_invite_public_page(
                    token=token,
                    inv=inv,
                    heading="Invito scaduto",
                    message="Questo invito non è più valido. Chiedi alla cantina di inviare un nuovo invito.",
                    show_auth_ctas=False,
                )
            if not inv.get("winery_id"):
                return _studio_invite_public_page(
                    token=token,
                    inv=inv,
                    heading="Invito non valido",
                    message="L'invito non contiene una cantina valida.",
                    show_auth_ctas=False,
                )

            email_error = _studio_invite_email_error(inv, user)
            if email_error:
                return _studio_invite_public_page(
                    token=token,
                    inv=inv,
                    heading="Account non corretto per questo invito",
                    message=email_error,
                    show_auth_ctas=False,
                    show_logout_cta=True,
                )

            _accept_studio_invite_row(cur, inv, studio_user_id, ts)
            conn.commit()

    return RedirectResponse(_invite_redirect_target(inv), status_code=303)
