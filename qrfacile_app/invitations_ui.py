from __future__ import annotations

import hashlib
import hmac
import os
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from qrfacile_app.auth_core import get_current_user, require_any_role
from qrfacile_app.csrf_core import csrf_input, require_csrf
from qrfacile_app.services.invitations import create_invitation, get_invitation, revoke_invitation_access, revoke_or_resend
from qrfacile_app.ui_shell import esc, page, page_public

router = APIRouter(tags=["invitations"])
RESUME_COOKIE = "invite_resume"


def _resume_value(invite_id: int) -> str:
    secret = (os.getenv("SESSION_SECRET") or os.getenv("CSRF_SECRET") or "dev").encode()
    value = str(int(invite_id))
    return value + "." + hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def _resume_id(request: Request) -> int | None:
    value = request.cookies.get(RESUME_COOKIE) or ""
    try: raw_id, signature = value.split(".", 1)
    except ValueError: return None
    if not hmac.compare_digest(_resume_value(int(raw_id)), value): return None
    return int(raw_id)


def _current_user_or_none(request: Request):
    try: return get_current_user(request)
    except HTTPException as exc:
        if exc.status_code == 303: return None
        raise


def _status_copy(status: str) -> tuple[str, int]:
    return {
        "accepted": ("Invito già accettato", 200), "rejected": ("Invito rifiutato", 200),
        "expired": ("Questo invito è scaduto", 410), "revoked": ("Questo invito è stato revocato", 410),
    }.get(status, ("Invito non valido", 404))


def _landing(request: Request, invite: dict, token: str | None) -> HTMLResponse:
    status = str(invite["status"])
    if status != "pending":
        message, code = _status_copy(status)
        return HTMLResponse(page_public(title="QRFACILE · Invito", subtitle="Invito", body_html=f"<div class='card'><div class='h1'>{esc(message)}</div></div>"), status_code=code)
    user = _current_user_or_none(request)
    perms = invite.get("permissions_json") or {}
    permission_names = [name for key,name in (("can_view","visualizzazione"),("can_edit","modifica"),("can_create","creazione"),("can_manage_labels","gestione etichette")) if perms.get(key)]
    target = {"studio":"collaborazione con la cantina","winery":"collaborazione con lo studio","label":"gestione di una singola etichetta","wine":"gestione di un singolo vino/lotto","collaborator":"collaborazione interna"}.get(invite["invite_type"],invite["invite_type"])
    if user:
        mismatch = str(user.get("email") or "").lower() != str(invite["invitee_email"]).lower()
        actions = "<div class='note note-err'>Questo invito è destinato a un altro indirizzo email.</div>" if mismatch else f"""
          <form method='post' action='/app/invite/decide'>{csrf_input(request)}<input type='hidden' name='decision' value='accept'><button class='btn btn-primary'>Accetta invito</button></form>
          <form method='post' action='/app/invite/decide'>{csrf_input(request)}<input type='hidden' name='decision' value='reject'><button class='btn'>Rifiuta</button></form>"""
    else:
        register_path = "/register-winery" if invite["invite_type"] == "winery" else "/register-studio"
        actions = f"<a class='btn btn-primary' href='/login?next=/app/invite/resume'>Accedi per accettare</a> <a class='btn' href='{register_path}?next=/app/invite/resume'>Registrati per accettare</a>"
    body = f"""<section style='max-width:760px;margin:32px auto'><div class='card'>
      <div class='h1'>Sei stato invitato</div><div class='p'><b>{esc(invite['inviter_email'])}</b> ti invita per: {esc(target)}.</div>
      <div class='note'>Cantina: <b>{esc(invite.get('winery_name') or 'da registrare')}</b><br>Permessi: {esc(', '.join(permission_names) or 'nessuno')}<br>Scadenza: {esc(str(invite['expires_at']))}<br>La pubblicazione e la delega non vengono concesse.</div>
      <div class='row' style='margin-top:18px'>{actions}</div></div></section>"""
    response = HTMLResponse(page_public(title="QRFACILE · Invito",subtitle="Invito",body_html=body))
    response.set_cookie(RESUME_COOKIE,_resume_value(invite["id"]),httponly=True,samesite="lax",secure=request.url.scheme=="https",max_age=1800,path="/")
    return response


@router.get("/app/invite/{invite_type}/accept/{token}", response_class=HTMLResponse)
def typed_invitation_landing(request: Request, invite_type: str, token: str):
    invite = get_invitation(token)
    if invite_type != invite["invite_type"] and not (invite_type == "studio" and invite["invite_type"] in {"label","wine"}):
        raise HTTPException(404,"Invito non valido")
    return _landing(request,invite,token)


@router.get("/app/invite/resume", response_class=HTMLResponse)
def resume_invitation(request: Request):
    invite_id = _resume_id(request)
    if not invite_id: raise HTTPException(404,"Riferimento invito scaduto: riapri il link ricevuto")
    from qrfacile_app.db import pg
    with pg() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT token_hash FROM invites WHERE id=%s",(invite_id,)); row=cur.fetchone()
    if not row: raise HTTPException(404,"Invito non valido")
    # Resume never reconstructs or exposes the raw token. Decisions resolve the signed invite id.
    invite = _invite_by_id(invite_id)
    return _landing(request,invite,None)


def _invite_by_id(invite_id: int) -> dict:
    from qrfacile_app.db import pg
    from psycopg.rows import dict_row
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""SELECT i.*,w.name winery_name,u.email inviter_email FROM invites i LEFT JOIN wineries w ON w.id=i.winery_id JOIN users u ON u.id=i.inviter_user_id WHERE i.id=%s""",(invite_id,)); row=cur.fetchone()
    if not row: raise HTTPException(404,"Invito non valido")
    return dict(row)


@router.post("/app/invite/decide")
def invitation_decide(request: Request, decision: str=Form(...), csrf_token: str=Form("")):
    require_csrf(request,csrf_token); user=require_any_role(request,("studio","winery","admin"))
    invite_id=_resume_id(request)
    if not invite_id: raise HTTPException(404,"Riferimento invito scaduto")
    invite=_invite_by_id(invite_id)
    # The token is not retained in session/DB; use a transactional id-based decision path.
    from qrfacile_app.services.invitations import decide_invitation_by_id
    result=decide_invitation_by_id(invite_id=invite_id,user=user,decision=decision)
    response=RedirectResponse("/app/invitations?msg="+quote("Invito accettato correttamente" if result["status"]=="accepted" else "Invito rifiutato"),303)
    response.delete_cookie(RESUME_COOKIE,path="/"); return response


@router.post("/app/invitations/{invite_id}/revoke")
def revoke(request: Request,invite_id:int,csrf_token:str=Form("")):
    require_csrf(request,csrf_token); user=require_any_role(request,("winery","studio")); revoke_or_resend(invite_id=invite_id,actor=user)
    return RedirectResponse("/app/invitations?msg=Invito%20revocato",303)


@router.post("/app/invitations/{invite_id}/resend")
def resend(request: Request,invite_id:int,csrf_token:str=Form("")):
    require_csrf(request,csrf_token); user=require_any_role(request,("winery","studio")); result=revoke_or_resend(invite_id=invite_id,actor=user,resend=True)
    # Email delivery adapter consumes raw_token immediately; never persist or audit it.
    request.app.state.last_invite_delivery = {"invite_id":result["id"]}
    return RedirectResponse("/app/invitations?msg=Nuovo%20link%20generato",303)


@router.post("/app/invitations/{invite_id}/access/revoke")
def revoke_access(request:Request,invite_id:int,csrf_token:str=Form("")):
    require_csrf(request,csrf_token); user=require_any_role(request,("winery","studio")); revoke_invitation_access(invite_id=invite_id,actor=user)
    return RedirectResponse("/app/invitations?msg=Accesso%20revocato",303)


@router.get("/app/invitations",response_class=HTMLResponse)
def invitation_center(request:Request,msg:str=""):
    user=require_any_role(request,("winery","studio","admin")); uid=int(user["id"])
    from qrfacile_app.db import pg
    from psycopg.rows import dict_row
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""SELECT i.id,i.invite_type,i.invitee_email,i.status,i.expires_at,i.created_at,
                         i.inviter_user_id,i.permissions_json,w.name winery_name,u.email inviter_email
                         FROM invites i LEFT JOIN wineries w ON w.id=i.winery_id JOIN users u ON u.id=i.inviter_user_id
                         WHERE i.inviter_user_id=%s OR i.recipient_user_id=%s OR lower(i.invitee_email)=lower(%s)
                         ORDER BY i.created_at DESC LIMIT 200""",(uid,uid,user["email"])); rows=[dict(r) for r in cur.fetchall()]
    cards=[]
    for item in rows:
        sent=int(item["inviter_user_id"])==uid
        actions=""
        if sent and item["status"]=="pending":
            actions=f"<form method='post' action='/app/invitations/{item['id']}/resend'>{csrf_input(request)}<button class='btn'>Reinvia</button></form><form method='post' action='/app/invitations/{item['id']}/revoke'>{csrf_input(request)}<button class='btn'>Revoca</button></form>"
        elif sent and item["status"]=="accepted": actions=f"<form method='post' action='/app/invitations/{item['id']}/access/revoke'>{csrf_input(request)}<button class='btn'>Revoca accesso</button></form>"
        elif not sent and item["status"]=="pending": actions="<a class='btn btn-primary' href='/app/invite/resume'>Apri</a>"
        cards.append(f"<article class='card'><div class='h2'>{esc(item['invite_type'])} · {esc(item.get('winery_name') or 'Cantina da registrare')}</div><div class='p'>Mittente: {esc(item['inviter_email'])}<br>Destinatario: {esc(item['invitee_email'])}<br>Stato: <b>{esc(item['status'])}</b> · scadenza {esc(str(item['expires_at']))}</div><div class='row'>{actions}</div></article>")
    create=""
    if str(user.get("role"))=="winery":
        create=f"""<form class='card' method='post' action='/app/invitations'>{csrf_input(request)}<div class='h2'>Nuovo invito</div><input class='input' type='email' name='recipient_email' required placeholder='email destinatario'><select class='input' name='invite_type'><option value='studio'>Studio grafico</option><option value='collaborator'>Collaboratore interno</option><option value='wine'>Singolo vino</option><option value='label'>Singola etichetta</option></select><input class='input' type='number' name='wine_id' placeholder='ID vino (se applicabile)'><input class='input' type='number' name='label_id' placeholder='ID etichetta (se applicabile)'><select class='input' name='preset'><option value='view'>Visualizzazione</option><option value='graphic'>Modifica grafica</option><option value='full'>Creazione e modifica</option></select><button class='btn btn-primary'>Crea invito</button></form>"""
    body=f"<div class='h1'>Centro inviti</div><div class='p'>Inviti inviati e ricevuti, senza esposizione dei token.</div>{create}<div style='display:grid;gap:12px;margin-top:16px'>{''.join(cards) or '<div class=\"card\">Nessun invito.</div>'}</div>"
    return HTMLResponse(page(
        title="Centro inviti",
        subtitle="Inviti inviati e ricevuti",
        body_html=body,
        msg=msg,
        user_email=str(user.get("email") or ""),
        role=str(user.get("role") or ""),
        credits=user.get("credits") if isinstance(user.get("credits"), dict) else None,
    ))


@router.post("/app/invitations",response_class=HTMLResponse)
def create(request:Request,recipient_email:str=Form(...),invite_type:str=Form(...),preset:str=Form("view"),wine_id:int|None=Form(None),label_id:int|None=Form(None),csrf_token:str=Form("")):
    require_csrf(request,csrf_token); user=require_any_role(request,("winery",))
    from qrfacile_app.db import pg
    with pg() as conn:
        with conn.cursor() as cur: cur.execute("SELECT id FROM wineries WHERE owner_user_id=%s",(user["id"],)); row=cur.fetchone()
    if not row: raise HTTPException(403,"Cantina non trovata")
    profiles={"view":{"can_view":True},"graphic":{"can_view":True,"can_edit":True,"can_manage_labels":True},"full":{"can_view":True,"can_edit":True,"can_create":True,"can_manage_labels":True}}
    result=create_invitation(invite_type=invite_type,inviter=user,recipient_email=recipient_email,winery_id=int(row[0]),wine_id=wine_id,label_id=label_id,permissions=profiles.get(preset,{}))
    base=(getattr(request.app.state,"app_base_url","") or f"{request.url.scheme}://{request.headers.get('host','')}").rstrip('/')
    link=f"{base}/app/invite/{result['invite_type']}/accept/{result.pop('raw_token')}"
    return HTMLResponse(page(
        title="Invito creato",
        subtitle="Condivisione sicura dell'accesso",
        body_html=f"<div class='card'><div class='h1'>Invito creato</div><div class='p'>Questo link viene mostrato una sola volta.</div><input class='input' readonly value='{esc(link)}'><a class='btn' href='/app/invitations'>Centro inviti</a></div>",
        user_email=str(user.get("email") or ""),
        role=str(user.get("role") or ""),
        credits=user.get("credits") if isinstance(user.get("credits"), dict) else None,
    ))
