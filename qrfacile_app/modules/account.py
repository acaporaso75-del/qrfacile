"""One account, several modules: which modules a user has, the last one used,
and activating Wine from an account created for another module."""
from __future__ import annotations

import time
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import csrf_input, require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.legal_core import has_link_acceptance
from qrfacile_app.ui_shell import esc, page

router = APIRouter()
KNOWN_MODULES = ("wine", "link")
FREE_WINE_CREDITS = 3
WINE_ROLES = ("winery", "studio", "admin", "collaborator")


def user_modules(cur, user: dict) -> dict[str, bool]:
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])
    wine = role in WINE_ROLES
    if not wine:
        cur.execute("SELECT 1 FROM wineries WHERE owner_user_id=%s LIMIT 1", (uid,))
        wine = cur.fetchone() is not None
    link = role == "admin"
    if not link:
        try:
            link = has_link_acceptance(cur, uid)
        except Exception:  # noqa: BLE001 - legal tables missing: Link not in use
            link = False
    return {"wine": bool(wine), "link": bool(link)}


def modules_for(user: dict) -> dict[str, bool]:
    try:
        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                return user_modules(cur, user)
    except Exception:  # noqa: BLE001 - the menu must render even if this fails
        role = (user.get("role") or "").lower().strip()
        return {"wine": role in WINE_ROLES, "link": role == "admin"}


def remember_module(user_id: int, key: str) -> None:
    """Best effort: where to land at the next login."""
    if key not in KNOWN_MODULES:
        return
    try:
        with pg() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET last_module=%s WHERE id=%s", (key, int(user_id)))
            conn.commit()
    except Exception:  # noqa: BLE001 - column missing before the migration
        pass


@router.get("/app/modules/wine/activate", response_class=HTMLResponse)
def wine_activate_get(request: Request, err: str = ""):
    user = require_any_role(request, ("business",) + WINE_ROLES)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if user_modules(cur, user)["wine"]:
                return RedirectResponse("/app/dashboard", status_code=303)
            cur.execute("SELECT to_jsonb(u)->>'display_name' AS name FROM users u WHERE id=%s", (int(user["id"]),))
            name = (cur.fetchone() or {}).get("name") or ""
    body = f"""
    <section class="card" style="max-width:680px">
      <h2 class="h2">Attiva QRFacile Wine</h2>
      <p class="p">Etichette digitali del vino: valori nutrizionali, ingredienti, allergeni e riciclo in un QR
      che stampi una volta. Ricevi <b>{FREE_WINE_CREDITS} QR vino gratuiti</b> per iniziare.</p>
      <p class="p">Il tuo account resta lo stesso: continui a usare anche i moduli che hai già.</p>
      <form method="post" action="/app/modules/wine/activate" style="display:grid;gap:12px">
        {csrf_input(request)}
        <div><label for="wa-name">Nome della cantina</label>
          <input id="wa-name" class="input" name="name" maxlength="120" required value="{esc(name)}"></div>
        <p class="muted" style="font-size:14px">I dati fiscali li completi dopo, nelle impostazioni della cantina,
        solo quando acquisti un pacchetto.</p>
        <button class="btn btn-primary" type="submit">Attiva Wine</button>
      </form>
    </section>
    """
    return HTMLResponse(page(
        title="QRFACILE · Attiva Wine", subtitle="Aggiungi un modulo al tuo account", body_html=body,
        err=err, role=user.get("role", ""), user_email=user.get("email", ""), credits=None,
    ))


@router.post("/app/modules/wine/activate")
def wine_activate_post(request: Request, name: str = Form("")):
    require_csrf_or_same_origin(request)
    user = require_any_role(request, ("business",) + WINE_ROLES)
    uid = int(user["id"])
    name = " ".join((name or "").split())[:120]
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtext('wine-activate'), %s)", (uid,))
            if user_modules(cur, user)["wine"]:
                conn.rollback()
                return RedirectResponse("/app/dashboard", status_code=303)
            if not name:
                conn.rollback()
                return RedirectResponse(f"/app/modules/wine/activate?err={quote('Indica il nome della cantina')}", status_code=303)
            now = int(time.time())
            cur.execute(
                "INSERT INTO wineries (owner_user_id, name, billing_country, created_at) VALUES (%s, %s, 'IT', %s)",
                (uid, name, now),
            )
            cur.execute(
                """INSERT INTO credit_ledger (user_id, credit_type, delta, reason, ref_table, ref_id, created_at)
                   VALUES (%s, 'wine', %s, 'seed', 'users', %s, %s)""",
                (uid, FREE_WINE_CREDITS, uid, now),
            )
            if (user.get("role") or "").lower() == "business":
                # A winery account keeps Link: /app/link accepts the winery role.
                cur.execute("UPDATE users SET role='winery' WHERE id=%s AND role='business'", (uid,))
            cur.execute("UPDATE users SET last_module='wine' WHERE id=%s", (uid,))
        conn.commit()
    return RedirectResponse("/app/dashboard", status_code=303)
