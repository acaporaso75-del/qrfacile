from urllib.parse import urlencode

from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse
from qrfacile_app.auth_core import require_any_role

router = APIRouter()

_LEGACY_PNG_PRESETS = {
    (20, 300): "label_std",
    (25, 600): "label_pro",
    (30, 300): "carton",
    (40, 300): "fair",
}


def _legacy_preset(fmt: str, size_mm: int, dpi: int) -> str:
    normalized = str(fmt or "png").lower().strip()
    if normalized in {"jpg", "jpeg", "png"}:
        return _LEGACY_PNG_PRESETS.get((int(size_mm), int(dpi)), "label_pro")
    if normalized == "svg":
        return "vector_svg"
    if normalized == "pdf":
        return "square_pdf"
    if normalized == "pdf_a4":
        return "a4_pdf"
    return "label_pro"

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

    preset = _legacy_preset(fmt, size_mm, dpi)
    query = urlencode({"preset": preset, "name": str(name or "qrfacile")})
    url = f"/app/wine/{wine_id}/export/file?{query}"
    return RedirectResponse(url, status_code=307)
