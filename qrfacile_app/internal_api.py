from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request

from qrfacile_app.internal_auth import require_internal_token
from qrfacile_app.services.compliance_service import (
    AI_POLICY_VERSION,
    get_compliance_status,
)


router = APIRouter(prefix="/internal/v1", tags=["internal-api"])


@router.get("/health")
def internal_health(request: Request):
    require_internal_token(request)
    return {
        "ok": True,
        "service": "qrfacile",
        "api_version": "v1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/compliance/status")
def internal_compliance_status(request: Request):
    require_internal_token(request)
    result = get_compliance_status()
    result["api_version"] = "v1"
    result["ai_policy_version"] = AI_POLICY_VERSION
    return result
