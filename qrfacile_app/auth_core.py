import time
from typing import Iterable, Optional, Dict, Any
from urllib.parse import quote

from fastapi import Request, HTTPException
from psycopg.rows import dict_row

from qrfacile_app.db import pg

COOKIE = "session_token"


def now() -> int:
    return int(time.time())


# ---------------------------------------------------------
# Redirect / error helpers
# ---------------------------------------------------------

def _redirect_login(request: Optional[Request] = None) -> None:
    """
    Redirect pulito verso la login quando l'utente non è autenticato.
    Preserva la destinazione richiesta in next, così il login può riportare
    l'utente alla pagina protetta dopo l'accesso.
    """
    location = "/login?expired=1"
    if request is not None:
        try:
            next_url = request.url.path
            if request.url.query:
                next_url = f"{next_url}?{request.url.query}"
            location = f"/login?next={quote(next_url, safe='/')}"
        except Exception:
            location = "/login?expired=1"

    raise HTTPException(
        status_code=303,
        detail="Login richiesto",
        headers={"Location": location},
    )


def _forbidden() -> None:
    raise HTTPException(status_code=403, detail="Accesso non autorizzato")


# ---------------------------------------------------------
# Session lookup
# Supporta sia sessions sia app_sessions
# ---------------------------------------------------------

def _session_user_id(token: str) -> Optional[int]:
    if not token:
        return None

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Prima prova app_sessions, se esiste
            try:
                cur.execute(
                    "SELECT user_id FROM app_sessions WHERE token=%s LIMIT 1",
                    (token,),
                )
                r = cur.fetchone()
                if r and r.get("user_id"):
                    return int(r["user_id"])
            except Exception:
                # app_sessions può non esistere in alcune installazioni
                conn.rollback()

            # Fallback su sessions
            try:
                cur.execute(
                    "SELECT user_id FROM sessions WHERE token=%s LIMIT 1",
                    (token,),
                )
                r = cur.fetchone()
                if r and r.get("user_id"):
                    return int(r["user_id"])
            except Exception:
                conn.rollback()

    return None


def _load_user(user_id: int) -> Optional[Dict[str, Any]]:
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id, email, role
                FROM users
                WHERE id=%s
                LIMIT 1
                """,
                (int(user_id),),
            )
            return cur.fetchone()


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def get_current_user(request: Request) -> Dict[str, Any]:
    """
    Restituisce l'utente corrente: {id, email, role}.
    Se non è loggato, reindirizza alla login.
    Cache per-request in request.state.
    """
    cached = getattr(request.state, "_auth_user", None)
    if cached:
        return cached

    token = request.cookies.get(COOKIE) or ""
    uid = _session_user_id(token)

    if not uid:
        _redirect_login(request)

    u = _load_user(uid)

    if not u:
        _redirect_login(request)

    request.state._auth_user = u
    request.state._auth_token = token
    return u


def require_any_role(
    request: Request,
    roles: Iterable[str],
    *,
    winery_id: Optional[int] = None,
    need: str = "view",
) -> Dict[str, Any]:
    """
    Gate centrale di autenticazione/autorizzazione.

    roles:
      ruoli ammessi, esempio ("winery", "studio", "admin")

    winery_id:
      se valorizzato e l'utente è uno studio, controlla i permessi su studio_clients

    need:
      "view" | "edit" | "create"

    Ritorna:
      dict utente

    Se non loggato:
      redirect a /login?expired=1

    Se non autorizzato:
      403
    """
    u = get_current_user(request)

    role = (u.get("role") or "").lower().strip()
    roles_set = {r.lower().strip() for r in roles}

    if role not in roles_set:
        _forbidden()

    # Admin sempre autorizzato
    if role == "admin":
        return u

    # Controllo permessi studio solo se viene passato winery_id
    if role == "studio" and winery_id is not None:
        _require_studio_permission(
            studio_user_id=int(u["id"]),
            winery_id=int(winery_id),
            need=need,
        )

    return u


# ---------------------------------------------------------
# Studio permissions
# ---------------------------------------------------------

def _require_studio_permission(studio_user_id: int, winery_id: int, need: str) -> None:
    need = (need or "view").lower().strip()

    if need not in ("view", "edit", "create"):
        need = "view"

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT can_view, can_edit, can_create
                FROM studio_clients
                WHERE studio_user_id=%s
                  AND winery_id=%s
                LIMIT 1
                """,
                (int(studio_user_id), int(winery_id)),
            )
            r = cur.fetchone()

    if not r:
        _forbidden()

    if need == "view" and not bool(r.get("can_view")):
        _forbidden()

    if need == "edit" and not bool(r.get("can_edit")):
        _forbidden()

    if need == "create" and not bool(r.get("can_create")):
        _forbidden()


def studio_allowed_wineries(studio_user_id: int, *, need: str = "view") -> list[int]:
    """
    Restituisce la lista degli winery_id accessibili dallo studio.

    need:
      view/edit/create filtra sulla colonna corrispondente.
    """
    need = (need or "view").lower().strip()

    col = "can_view"
    if need == "edit":
        col = "can_edit"
    elif need == "create":
        col = "can_create"

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                SELECT winery_id
                FROM studio_clients
                WHERE studio_user_id=%s
                  AND {col}=TRUE
                ORDER BY winery_id
                """,
                (int(studio_user_id),),
            )
            return [int(x["winery_id"]) for x in (cur.fetchall() or [])]


def winery_id_for_owner(user_id: int) -> Optional[int]:
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id
                FROM wineries
                WHERE owner_user_id=%s
                LIMIT 1
                """,
                (int(user_id),),
            )
            r = cur.fetchone()

    return int(r["id"]) if r else None
