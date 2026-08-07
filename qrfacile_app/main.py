import logging
import os
import warnings
from importlib import import_module

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from qrfacile_app.compliance_score_middleware import ComplianceScoreMiddleware
from qrfacile_app.public_recycling_catalog_middleware import PublicRecyclingCatalogMiddleware
from qrfacile_app.runtime_config import get_runtime_config
from qrfacile_app.security_middleware import SecurityHeadersMiddleware
from qrfacile_app.uploads_routes import VersionedUploadStaticFiles

logger = logging.getLogger("qrfacile.main")
logging.basicConfig(level=logging.INFO)

RUNTIME_CONFIG = get_runtime_config(validate=True)

app = FastAPI(title="QRFACILE")
app.state.app_base_url = RUNTIME_CONFIG.app_base_url
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PublicRecyclingCatalogMiddleware)
app.add_middleware(ComplianceScoreMiddleware)

APP_ROOT = str(RUNTIME_CONFIG.app_root)
STATIC_DIR = str(RUNTIME_CONFIG.static_dir)
UPLOADS_DIR = str(RUNTIME_CONFIG.uploads_dir)
TEMPLATES_DIR = str(RUNTIME_CONFIG.templates_dir)


def _mount_directory(url_path: str, directory: str, *, name: str, uploads: bool = False) -> None:
    if not os.path.isdir(directory):
        message = f"Directory obbligatoria non disponibile: {name}={directory}"
        if RUNTIME_CONFIG.environment == "staging":
            raise RuntimeError(message)
        logger.warning(message)
        return

    static_class = VersionedUploadStaticFiles if uploads else StaticFiles
    try:
        app.mount(url_path, static_class(directory=directory), name=name)
        logger.info("Mounted %s -> %s", url_path, directory)
    except Exception as exc:
        if RUNTIME_CONFIG.environment == "staging":
            raise RuntimeError(f"Mount obbligatorio fallito: {name}") from exc
        logger.warning("Mount %s non disponibile: %s", name, exc)


_mount_directory("/static", STATIC_DIR, name="static")
_mount_directory("/uploads", UPLOADS_DIR, name="uploads", uploads=True)


MANDATORY_ROUTERS = frozenset(
    {
        "qrfacile_app.auth_routes",
        "qrfacile_app.email_verification_ui",
        "qrfacile_app.landing_routes",
        "qrfacile_app.health",
        "qrfacile_app.start_ui",
        "qrfacile_app.dashboard_ui",
        "qrfacile_app.label_media_ui",
        "qrfacile_app.collaboration_management_ui",
        "qrfacile_app.invitation_management_ui",
        "qrfacile_app.invitations_ui",
        "qrfacile_app.invitation_acceptance_ui",
        "qrfacile_app.invitation_center_ui",
        "qrfacile_app.secure_publish_ui",
        "qrfacile_app.recycling_validation_ui",
        "qrfacile_app.wine_compliance_engine_ui",
        "qrfacile_app.studio_register_routes",
        "qrfacile_app.winery_register_routes",
        "qrfacile_app.public",
        "qrfacile_app.uploads_routes",
    }
)


def include_router_safe(module_path: str, router_attr: str = "router") -> None:
    required = module_path in MANDATORY_ROUTERS
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="'crypt' is deprecated.*",
                category=DeprecationWarning,
            )
            m = import_module(module_path)
        r = getattr(m, router_attr, None)
        if r is None:
            if required:
                raise RuntimeError(f"Router obbligatorio assente: {module_path}.{router_attr}")
            logger.warning("Router opzionale assente: %s", module_path)
            return
        app.include_router(r)
        logger.info("Included %s router: %s", "mandatory" if required else "optional", module_path)
    except Exception as exc:
        if required:
            raise RuntimeError(f"Caricamento router obbligatorio fallito: {module_path}") from exc
        logger.warning("Router opzionale non caricato: %s (%s)", module_path, exc)


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
          <div class="h2">{title}</div><div class="p">{msg or ""}</div>
          <div class="row" style="margin-top:14px">
            <a class="btn btn-primary" href="/app/start">Menu</a>
            <a class="btn" href="/app/dashboard">Dashboard</a>
            <a class="btn" href="/login">Login</a>
          </div>
        </div>"""
        html = f"""<!doctype html><html lang="it"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>QRFACILE · {title}</title><link rel="stylesheet" href="/static/app.css"></head><body><div class="shell" style="grid-template-columns:1fr;max-width:980px"><main class="content">{body}</main></div></body></html>"""
        return HTMLResponse(html, status_code=code)
    return HTMLResponse(str(exc.detail), status_code=code, headers=dict(exc.headers or {}))


include_router_safe("qrfacile_app.auth_routes")
include_router_safe("qrfacile_app.email_verification_ui")
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
# Safe collaboration, invitation and publication mutations precede legacy routes with the same paths.
include_router_safe("qrfacile_app.collaboration_management_ui")
include_router_safe("qrfacile_app.invitation_management_ui")
include_router_safe("qrfacile_app.invitations_ui")
include_router_safe("qrfacile_app.invitation_acceptance_ui")
include_router_safe("qrfacile_app.invitation_center_ui")
include_router_safe("qrfacile_app.secure_publish_ui")
include_router_safe("qrfacile_app.label_acl_ui")
include_router_safe("qrfacile_app.collaboration_access_ui")
# Recycling validation and guidance routes must precede legacy compliance routes.
include_router_safe("qrfacile_app.recycling_validation_ui")
include_router_safe("qrfacile_app.recycling_guidance_ui")
include_router_safe("qrfacile_app.wine_compliance_ui")
include_router_safe("qrfacile_app.wine_compliance_engine_ui")
include_router_safe("qrfacile_app.wine_rule_catalog_ui")
include_router_safe("qrfacile_app.wine_knowledge_ui")
include_router_safe("qrfacile_app.wine_compliance_replay_ui")
include_router_safe("qrfacile_app.wine_compliance_advisor_ui")
include_router_safe("qrfacile_app.wine_compliance_center_ui")
include_router_safe("qrfacile_app.wine_flow_ui")
include_router_safe("qrfacile_app.wine_hub_ui")
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
