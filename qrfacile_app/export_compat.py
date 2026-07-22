from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse
from qrfacile_app.auth_core import require_any_role

router = APIRouter()

@router.get("/app/export/{wine_id}")
def export_compat(
    request: Request,
    wine_id: int,
    fmt: str = Query("png"),
    size_mm: int = Query(25),
    dpi: int = Query(300),
    name: str = Query("qrfacile"),
):
    """
    Compat endpoint:
    old links: /app/export/{id}?fmt=png|svg|pdf|jpg
    new: /app/wine/{id}/export/file?fmt=...
    """
    require_any_role(request, ["winery"])

    fmt = (fmt or "png").lower().strip()
    # se qualcuno chiede jpg, lo mappiamo a png (v1) per non rompere
    if fmt == "jpg" or fmt == "jpeg":
        fmt = "png"

    url = f"/app/wine/{wine_id}/export/file?fmt={fmt}&size_mm={int(size_mm)}&dpi={int(dpi)}&name={name}"
    return RedirectResponse(url, status_code=307)
