import logging
import os
from importlib import import_module

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from qrfacile_app.security_middleware import SecurityHeadersMiddleware

logger = logging.getLogger("qrfacile.main")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="QRFACILE")
app.state.app_base_url = os.getenv("APP_BASE_URL", "").rstrip("/")
app.add_middleware(SecurityHeadersMiddleware)

APP_ROOT = os.getenv("APP_ROOT", "/opt/qrfacile")
STATIC_DIR = os.getenv("STATIC_DIR", f"{APP_ROOT}/static")
UPLOADS_DIR = os.getenv("UPLOADS_DIR", f"{APP_ROOT}/uploads")

try:
    if os.path.isdir(STATIC_DIR):
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
        logger.info("Mounted /static -> %s", STATIC_DIR)
except Exception as e:
    logger.warning("Skip static mount: %s", e)

try:
    if os.path.isdir(UPLOADS_DIR):
        app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")
        logger.info("Mounted /uploads -> %s", UPLOADS_DIR)
except Exception as e:
    logger.warning("Skip uploads mount: %s", e)


def include_router_safe(module_path: str, router_attr: str = "router") -> None:
    try:
        m = import_module(module_path)
        r = getattr(m, router_attr, None)
        if r is None:
            logger.warning("Skip module (no router): %s", module_path)
            return
        app.include_router(r)
        logger.info("Included router: %s", module_path)
    except Exception as e:
        logger.warning("Skip module %s (%s)", module_path, e)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code = exc.status_code
    msg = (exc.detail or "").strip()

    if 300 <= code < 400:
        return Response(status_code=code, headers=dict(exc.headers or {}))

    if code in (404, 405, 403):
        title = "Pagina non trovata" if code == 404 else ("Metodo non consentito" if code == 405 else "Accesso negato")
        body = f"""
        <div class="card" style="margin-top:14px;max-width:860px">
          <div class="h2">{title}</div>
          <div class="p">{msg or ""}</div>
          <div class="row" style="margin-top:14px">
            <a class="btn btn-primary" href="/app/start">Menu</a>
            <a class="btn" href="/app/dashboard">Dashboard</a>
            <a class="btn" href="/login">Login</a>
          </div>
        </div>
        """
        html = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>QRFACILE · {title}</title><link rel="stylesheet" href="/static/app.css"></head>
<body><div class="shell" style="grid-template-columns:1fr;max-width:980px"><main class="content">{body}</main></div></body></html>"""
        return HTMLResponse(html, status_code=code)

    return HTMLResponse(str(exc.detail), status_code=code, headers=dict(exc.headers or {}))


include_router_safe("qrfacile_app.auth_routes")
include_router_safe("qrfacile_app.landing_routes")
include_router_safe("qrfacile_app.pricing_ui")
include_router_safe("qrfacile_app.legal_pages")
include_router_safe("qrfacile_app.compliance_ui")
include_router_safe("qrfacile_app.legal_acceptance_ui")
include_router_safe("qrfacile_app.privacy_requests_ui")
include_router_safe("qrfacile_app.compliance_incidents_ui")
include_router_safe("qrfacile_app.ai_review_ui")
include_router_safe("qrfacile_app.ai_registry_ui")
include_router_safe("qrfacile_app.internal_api")
include_router_safe("qrfacile_app.guide_pages")
include_router_safe("qrfacile_app.context_ui")
include_router_safe("qrfacile_app.health")
include_router_safe("qrfacile_app.admin_system_ui")
include_router_safe("qrfacile_app.start_ui")
include_router_safe("qrfacile_app.dashboard_ui")
include_router_safe("qrfacile_app.billing_ui")
include_router_safe("qrfacile_app.paypal_ui")
include_router_safe("qrfacile_app.external_qr_ui")
include_router_safe("qrfacile_app.premium_ui")
include_router_safe("qrfacile_app.label_hub_ui")
include_router_safe("qrfacile_app.label_media_ui")
include_router_safe("qrfacile_app.label_compliance_ui")
include_router_safe("qrfacile_app.label_history_ui")
include_router_safe("qrfacile_app.label_acl_ui")
include_router_safe("qrfacile_app.wine_hub_ui")
include_router_safe("qrfacile_app.wine_compliance_ui")
include_router_safe("qrfacile_app.wine_images_ui")
include_router_safe("qrfacile_app.studio_area")
include_router_safe("qrfacile_app.studio_home_ui")
include_router_safe("qrfacile_app.studio_settings_ui")
include_router_safe("qrfacile_app.studio_register_routes")
include_router_safe("qrfacile_app.studio_payout_ui")
include_router_safe("qrfacile_app.winery_register_routes")
include_router_safe("qrfacile_app.winery_settings_ui")
include_router_safe("qrfacile_app.winery_logo_ui")
include_router_safe("qrfacile_app.admin_home_ui")
include_router_safe("qrfacile_app.admin_payouts_ui")
include_router_safe("qrfacile_app.admin_credits_ui")
include_router_safe("qrfacile_app.admin_customer_ui")
include_router_safe("qrfacile_app.admin_legacy_ui")
include_router_safe("qrfacile_app.admin_override_requests_ui")
include_router_safe("qrfacile_app.public")
include_router_safe("qrfacile_app.publish_routes")
include_router_safe("qrfacile_app.uploads_routes")
include_router_safe("qrfacile_app.export_qr_ui")
include_router_safe("qrfacile_app.export_compat")
include_router_safe("qrfacile_app.send_print")
include_router_safe("qrfacile_app.labels_search")
include_router_safe("qrfacile_app.register_interest_routes")
include_router_safe("qrfacile_app.bulk_tools")
include_router_safe("qrfacile_app.wine_master_ui")
include_router_safe("qrfacile_app.legacy_routes")
