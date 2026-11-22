"""Public resolver of module QR codes: GET /d/<slug> (QRFacile Link).

A printed QR must always open its content: this route works whether or not
the ``link`` module switch is on, and before the vertical-modules migration
(rows with only ``payload.url``). Statistics are written in their own short
transaction; any failure there never blocks the response.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pathlib import Path

from fastapi.responses import FileResponse, HTMLResponse, Response
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.modules.content_types import CONTENT_TYPES
from qrfacile_app.modules.stats import record_scan
from qrfacile_app.modules.switches import is_enabled  # noqa: F401 - re-exported for callers/tests
from qrfacile_app.services.storage import get_uploads_dir
from qrfacile_app.ui_shell import esc

router = APIRouter()
log = logging.getLogger(__name__)

# to_jsonb keeps the query valid before the module columns exist.
_LOOKUP = """
SELECT q.id, q.status, q.payload,
       to_jsonb(q)->>'module' AS module,
       to_jsonb(q)->>'stats_level' AS stats_level
FROM qr_items q
WHERE q.slug=%s AND (q.qr_type='external' OR to_jsonb(q)->>'module'=%s)
LIMIT 1
"""


def not_found(slug: str = "") -> HTMLResponse:
    report = f"<p><a href='/segnala/{esc(slug)}'>Segnala contenuto</a></p>" if slug else ""
    html = (
        "<!doctype html><html lang='it'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'><title>QR non attivo</title>"
        "<link rel='stylesheet' href='/static/app.css'></head><body>"
        "<main style='max-width:640px;margin:60px auto;padding:24px'>"
        "<div class='card'><h1 class='h1'>QR non attivo</h1>"
        "<p>Questo QR non è collegato a nessun contenuto.</p>"
        f"{report}</div></main></body></html>"
    )
    return HTMLResponse(html, status_code=404, headers={"Cache-Control": "no-store"})


def _content(payload: dict) -> tuple[str, dict] | None:
    kind = payload.get("type") or "link"
    content = (payload.get("content") or {}).get(kind)
    if kind == "link" and not content:
        content = {"url": payload.get("url") or ""}
    if kind not in CONTENT_TYPES or not isinstance(content, dict):
        return None
    if not CONTENT_TYPES[kind].is_complete(content):
        return None
    return kind, content


# Our own monitoring (scripts/check_historic_qr.py) must not inflate statistics.
_INTERNAL_PROBES = ("qrfacile-historic-qr-check",)


def _record(request: Request, qr_item_id: int, level: str) -> None:
    if level not in ("counts", "detailed"):
        return
    if request.headers.get("user-agent", "") in _INTERNAL_PROBES:
        return
    try:
        with pg() as conn:
            with conn.cursor() as cur:
                # A slow statistics write must never hold up the scan.
                cur.execute("SET LOCAL statement_timeout = '300ms'")
                record_scan(
                    cur,
                    qr_item_id=qr_item_id,
                    level=level,
                    user_agent=request.headers.get("user-agent", ""),
                    accept_language=request.headers.get("accept-language", ""),
                    now=datetime.now(timezone.utc),
                )
            conn.commit()
    except Exception:  # noqa: BLE001 - statistics must never block a scan
        log.warning("module scan statistics not recorded", exc_info=True)


def _active_row(slug: str, module: str) -> dict | None:
    slug = (slug or "").strip()
    if not slug or len(slug) > 64 or "\x00" in slug:
        return None
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(_LOOKUP, (slug, module))
            row = cur.fetchone()
    if not row or str(row.get("status") or "").lower() != "attiva":
        return None
    return row


def module_logo(request: Request, slug: str, *, module: str = "link") -> Response:
    """Logo of an active mini-page. Module files are never public under /uploads."""
    row = _active_row(slug, module)
    payload = (row or {}).get("payload") if isinstance((row or {}).get("payload"), dict) else {}
    logo = str(((payload.get("content") or {}).get("minipage") or {}).get("logo") or "")
    expected_prefix = f"modules/{module}/{int(row['id'])}/" if row else ""
    if not row or not logo.startswith(expected_prefix) or ".." in logo:
        return not_found()
    path = Path(get_uploads_dir()) / logo
    if not path.is_file():
        return not_found()
    return FileResponse(path, media_type="image/png", headers={
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })


def module_asset(request: Request, slug: str, name: str, *, module: str = "link") -> Response:
    """Files of an active QR (gallery photos, calendar file): never public under /uploads."""
    row = _active_row(slug, module)
    payload = (row or {}).get("payload") if isinstance((row or {}).get("payload"), dict) else {}
    resolved = _content(payload or {}) if row else None
    if resolved is None:
        return not_found()
    kind, content = resolved
    serve = getattr(CONTENT_TYPES[kind], "asset_response", None)
    response = serve(content, name) if serve else None
    return response if response is not None else not_found()


def resolve_module_qr(request: Request, slug: str, *, module: str = "link") -> Response:
    slug = (slug or "").strip()
    if not slug or len(slug) > 64 or "\x00" in slug:
        return not_found()
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(_LOOKUP, (slug, module))
            row = cur.fetchone()
    if not row or str(row.get("status") or "").lower() != "attiva":
        return not_found(slug)
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    resolved = _content(payload)
    if resolved is None:
        return not_found(slug)
    kind, content = resolved
    try:
        response = CONTENT_TYPES[kind].public_response(content, slug=slug)
    except Exception:  # noqa: BLE001 - e.g. a PDF file missing on disk
        log.warning("module content not servable", exc_info=True)
        return not_found(slug)
    _record(request, int(row["id"]), row.get("stats_level") or "none")
    return response


@router.get("/d/{slug}")
def link_public(request: Request, slug: str):
    return resolve_module_qr(request, slug, module="link")


@router.get("/d/{slug}/a/{name}")
def link_asset(request: Request, slug: str, name: str):
    return module_asset(request, slug, name, module="link")


@router.get("/d/{slug}/logo")
def link_logo(request: Request, slug: str):
    return module_logo(request, slug, module="link")
