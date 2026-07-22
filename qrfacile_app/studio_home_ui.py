# /opt/qrfacile/qrfacile_app/studio_home_ui.py
#
# Compatibilità vecchia rotta Studio.
# La vera Area Studio ufficiale è in studio_area.py su /studio.
# Questo file resta solo per non rompere eventuali link esistenti.

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from qrfacile_app.auth_core import require_any_role

router = APIRouter()


@router.get("/studio/home")
def studio_home_redirect(request: Request):
    require_any_role(request, ("studio", "admin"))
    return RedirectResponse("/studio", status_code=303)
