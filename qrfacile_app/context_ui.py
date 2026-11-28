from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role, studio_allowed_wineries, winery_id_for_owner
from qrfacile_app.csrf_core import require_csrf_or_same_origin
from qrfacile_app.db import pg
from qrfacile_app.navigation_security import safe_local_path

router = APIRouter()

COOKIE_NAME = "active_winery_id"


def _admin_allowed_wineries(cur) -> list[int]:
    cur.execute("SELECT id FROM wineries ORDER BY id")
    return [int(r["id"]) for r in (cur.fetchall() or [])]


def _allowed_wineries(user: dict) -> list[int]:
    role = (user.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if role == "admin":
                return _admin_allowed_wineries(cur)

    if role == "studio":
        return studio_allowed_wineries(int(user["id"]), need="view")

    wid = winery_id_for_owner(int(user["id"]))
    return [wid] if wid else []


@router.post("/app/set-winery")
def set_winery(request: Request, winery_id: int = Form(...), next_url: str = Form("/app/dashboard")):
    require_csrf_or_same_origin(request)
    user = require_any_role(request, ("winery", "studio", "admin"))
    allowed = _allowed_wineries(user)

    if int(winery_id) not in allowed:
        raise HTTPException(403, "Cantina non consentita")

    target = safe_local_path(next_url)

    resp = RedirectResponse(target, status_code=303)
    resp.set_cookie(
        COOKIE_NAME,
        str(int(winery_id)),
        httponly=True,
        samesite="lax",
        secure=(request.url.scheme == "https"),
        path="/",
    )
    return resp


@router.post("/app/clear-winery")
def clear_winery(request: Request, next_url: str = Form("/app/dashboard")):
    require_csrf_or_same_origin(request)
    require_any_role(request, ("winery", "studio", "admin"))

    target = safe_local_path(next_url)

    resp = RedirectResponse(target, status_code=303)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp

