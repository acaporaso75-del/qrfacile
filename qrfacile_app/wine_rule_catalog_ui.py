from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.wine_rule_catalog import public_rule_catalog

router = APIRouter(tags=["wine-rule-catalog"])


@router.get("/api/admin/compliance/wine-rules", response_class=JSONResponse)
def wine_rule_catalog_api(request: Request):
    require_any_role(request, ("admin",))
    return JSONResponse(public_rule_catalog())
