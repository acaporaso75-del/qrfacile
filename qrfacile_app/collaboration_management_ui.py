from __future__ import annotations

from urllib.parse import quote_plus

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from qrfacile_app.audit_core import write_audit_event
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.services.collaboration_management import (
    assign_studio_to_label,
    clear_label_collaboration,
    revoke_studio_connection,
    update_studio_connection_profile,
)

router = APIRouter(tags=["collaboration-management"])


def _same_origin(request: Request) -> None:
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin:
        return
    expected = f"{request.url.scheme}://{request.headers.get('host', '')}".rstrip("/")
    if origin != expected:
        raise HTTPException(403, "Origine richiesta non valida")


def _return(url: str, *, msg: str = "", err: str = "") -> RedirectResponse:
    sep = "&" if "?" in url else "?"
    if msg:
        url = f"{url}{sep}msg={quote_plus(msg)}"
    elif err:
        url = f"{url}{sep}err={quote_plus(err)}"
    return RedirectResponse(url, status_code=303)


@router.post("/app/label/{label_id}/acl/assign")
def safe_label_assign(
    request: Request,
    label_id: int,
    studio_user_id: int = Form(...),
    profile: str = Form("graphic"),
):
    _same_origin(request)
    actor = require_any_role(request, ("winery", "admin"))
    result = assign_studio_to_label(
        actor=actor,
        label_id=label_id,
        studio_user_id=studio_user_id,
        profile=profile,
    )
    write_audit_event(
        action="label_collaborator_assigned",
        resource_type="wine_label",
        resource_id=label_id,
        actor=actor,
        request=request,
        metadata={
            "studio_user_id": studio_user_id,
            "profile": profile,
            "permissions": result["collaboration"],
            "old_studio": result["old_studio"],
            "new_studio": result["new_studio"],
        },
    )
    return _return(f"/app/wine/{result['label']['wine_id']}/access-center", msg="Studio assegnato all'etichetta")


@router.post("/app/label/{label_id}/acl/clear")
def safe_label_clear(request: Request, label_id: int):
    _same_origin(request)
    actor = require_any_role(request, ("winery", "admin"))
    result = clear_label_collaboration(actor=actor, label_id=label_id)
    write_audit_event(
        action="label_collaborator_removed",
        resource_type="wine_label",
        resource_id=label_id,
        actor=actor,
        request=request,
        metadata={
            "deactivated": result["deactivated"],
            "old_studio": result["old_studio"],
            "new_studio": None,
        },
    )
    return _return(f"/app/wine/{result['label']['wine_id']}/access-center", msg="Gestione interna attivata")


@router.post("/app/label/{label_id}/management/set")
def safe_label_management_set(
    request: Request,
    label_id: int,
    management_value: str = Form(...),
    return_to: str = Form(""),
):
    _same_origin(request)
    actor = require_any_role(request, ("winery", "admin"))
    value = str(management_value or "").strip().lower()
    if value == "invite":
        return RedirectResponse(f"/app/winery/settings?source_label_id={label_id}#invite-studio", status_code=303)
    if value == "self":
        result = clear_label_collaboration(actor=actor, label_id=label_id)
        write_audit_event(
            action="label_management_internal",
            resource_type="wine_label",
            resource_id=label_id,
            actor=actor,
            request=request,
            metadata={"old_studio": result["old_studio"], "new_studio": None},
        )
        return _return(return_to or f"/app/wine/{result['label']['wine_id']}/access-center", msg="Gestione interna attivata")
    if value.startswith("studio:"):
        try:
            studio_user_id = int(value.split(":", 1)[1])
        except ValueError as exc:
            raise HTTPException(422, "Studio non valido") from exc
        result = assign_studio_to_label(actor=actor, label_id=label_id, studio_user_id=studio_user_id, profile="graphic")
        write_audit_event(
            action="label_collaborator_assigned",
            resource_type="wine_label",
            resource_id=label_id,
            actor=actor,
            request=request,
            metadata={
                "studio_user_id": studio_user_id,
                "profile": "graphic",
                "old_studio": result["old_studio"],
                "new_studio": result["new_studio"],
            },
        )
        return _return(return_to or f"/app/wine/{result['label']['wine_id']}/access-center", msg="Studio assegnato")
    raise HTTPException(422, "Scelta gestione non valida")


@router.post("/app/settings/studios/set")
def safe_studio_permissions(
    request: Request,
    sc_id: int = Form(...),
    preset: str = Form(...),
):
    _same_origin(request)
    actor = require_any_role(request, ("winery", "admin"))
    updated = update_studio_connection_profile(actor=actor, studio_client_id=sc_id, profile=preset)
    write_audit_event(
        action="studio_permissions_changed",
        resource_type="studio_client",
        resource_id=sc_id,
        actor=actor,
        request=request,
        metadata=updated,
    )
    return _return("/app/winery/settings", msg="Permessi aggiornati e sincronizzati sulle etichette")


@router.post("/app/settings/studios/revoke")
def safe_studio_revoke(request: Request, sc_id: int = Form(...)):
    _same_origin(request)
    actor = require_any_role(request, ("winery", "admin"))
    result = revoke_studio_connection(actor=actor, studio_client_id=sc_id)
    write_audit_event(
        action="studio_winery_access_revoked",
        resource_type="studio_client",
        resource_id=sc_id,
        actor=actor,
        request=request,
        metadata=result,
    )
    return _return("/app/winery/settings", msg="Accesso revocato su cantina ed etichette")
