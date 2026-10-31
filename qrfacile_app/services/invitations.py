from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from fastapi import HTTPException
from psycopg.rows import dict_row

from qrfacile_app.db import pg

INVITE_TYPES = {"studio", "winery", "collaborator", "label", "wine"}
TERMINAL_STATES = {"accepted", "rejected", "revoked", "expired"}
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
MAX_SENDS = 10


def token_hash(raw: str) -> str:
    return hashlib.sha256((raw or "").encode()).hexdigest()


def validate_token(raw: str) -> str:
    if not TOKEN_RE.fullmatch(raw or ""):
        raise HTTPException(404, "Invito non valido")
    return token_hash(raw)


def normalize_permissions(value: Mapping[str, Any] | None) -> dict[str, bool]:
    source = value or {}
    view = bool(source.get("can_view", True))
    edit = view and bool(source.get("can_edit", False))
    create = view and bool(source.get("can_create", False))
    return {
        "can_view": view,
        "can_edit": edit,
        "can_create": create,
        "can_manage_labels": view and bool(source.get("can_manage_labels", edit)),
        # Publication and delegation are never granted by an invitation.
        "can_publish": False,
        "can_delegate": False,
    }


def _audit(cur, action: str, actor_id: int | None, invite_id: int, metadata: dict | None = None) -> None:
    cur.execute("SELECT role FROM users WHERE id=%s", (actor_id,)) if actor_id else None
    row = cur.fetchone() if actor_id else None
    cur.execute(
        """INSERT INTO audit_log(user_id,role,action,entity_type,entity_id,meta)
           VALUES (%s,%s,%s,'invite',%s,%s::jsonb)""",
        (actor_id, (row or {}).get("role"), action, invite_id,
         json.dumps(metadata or {}, ensure_ascii=False)),
    )


def create_invitation(*, invite_type: str, inviter: Mapping[str, Any], recipient_email: str,
                      winery_id: int | None, wine_id: int | None = None, label_id: int | None = None,
                      studio_id: int | None = None, permissions: Mapping[str, Any] | None = None,
                      ttl_days: int = 14) -> dict[str, Any]:
    kind = (invite_type or "").strip().lower()
    email = "".join((recipient_email or "").split()).lower()
    if kind not in INVITE_TYPES or "@" not in email:
        raise HTTPException(422, "Dati invito non validi")
    if not 1 <= int(ttl_days) <= 30:
        raise HTTPException(422, "Scadenza invito non valida")
    perms = normalize_permissions(permissions)
    raw = secrets.token_urlsafe(32)
    digest = token_hash(raw)
    now = datetime.now(timezone.utc)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            actor_id, role = int(inviter.get("id") or 0), str(inviter.get("role") or "").lower()
            winery = None
            if winery_id is not None:
                cur.execute("SELECT owner_user_id FROM wineries WHERE id=%s FOR SHARE", (winery_id,)); winery=cur.fetchone()
            if kind == "winery" and role == "studio" and winery_id is None:
                pass
            elif not winery:
                raise HTTPException(404, "Cantina non trovata")
            elif role != "winery" or actor_id != int(winery["owner_user_id"]):
                raise HTTPException(403, "Solo la cantina proprietaria può creare questo invito")
            cur.execute("SELECT count(*) n FROM invites WHERE inviter_user_id=%s AND created_at>now()-interval '1 hour'",(actor_id,))
            if int(cur.fetchone()["n"]) >= 20: raise HTTPException(429,"Troppi inviti: riprova più tardi")
            if label_id:
                cur.execute("SELECT 1 FROM wine_labels WHERE id=%s AND winery_id=%s", (label_id, winery_id))
                if not cur.fetchone(): raise HTTPException(404, "Etichetta non trovata")
            if wine_id:
                cur.execute("SELECT 1 FROM wine_labels WHERE wine_id=%s AND winery_id=%s LIMIT 1", (wine_id, winery_id))
                if not cur.fetchone(): raise HTTPException(404, "Vino non trovato")
            cur.execute(
                """UPDATE invites SET status='revoked',revoked_at=now(),revoked_by_user_id=%s
                   WHERE inviter_user_id=%s AND lower(invitee_email)=%s AND invite_type=%s
                     AND winery_id=%s AND label_id IS NOT DISTINCT FROM %s
                     AND wine_id IS NOT DISTINCT FROM %s AND status='pending'""",
                (actor_id, actor_id, email, kind, winery_id, label_id, wine_id),
            )
            cur.execute(
                """INSERT INTO invites(legacy_token,token_hash,invite_type,inviter_user_id,inviter_role,
                       invitee_email,target_role,winery_id,wine_id,label_id,studio_id,permissions_json,
                       status,expires_at,created_at,send_attempts)
                   VALUES(NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'pending',%s,%s,1)
                   RETURNING id,token_hash,invite_type,invitee_email,status,expires_at""",
                (digest, kind, actor_id, role, email,
                 "winery" if kind == "winery" else ("studio" if kind in {"studio","label","wine"} else "collaborator"),
                 winery_id, wine_id, label_id, studio_id, json.dumps(perms), now + timedelta(days=ttl_days), now),
            )
            result = dict(cur.fetchone())
            _audit(cur, "invitation_created", actor_id, result["id"], {"type": kind, "winery_id": winery_id})
        conn.commit()
    result["raw_token"] = raw
    return result


def get_invitation(raw: str, *, lock: bool = False, include_terminal: bool = True) -> dict[str, Any]:
    digest = validate_token(raw)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """SELECT i.*, w.name winery_name, u.email inviter_email
                   FROM invites i LEFT JOIN wineries w ON w.id=i.winery_id
                   JOIN users u ON u.id=i.inviter_user_id WHERE i.token_hash=%s LIMIT 1""" + (" FOR UPDATE OF i" if lock else ""),
                (digest,),
            )
            row = cur.fetchone()
    if not row: raise HTTPException(404, "Invito non valido")
    item = dict(row)
    if item["status"] == "pending" and item["expires_at"] <= datetime.now(timezone.utc):
        item["status"] = "expired"
    if not include_terminal and item["status"] != "pending":
        raise HTTPException(410 if item["status"] in {"expired","revoked"} else 409, f"Invito {item['status']}")
    return item


def _grant(cur, invite: dict, user_id: int) -> tuple[str, int]:
    perms = normalize_permissions(invite.get("permissions_json"))
    kind = invite["invite_type"]
    if kind in {"studio", "winery", "collaborator"}:
        if kind == "winery" and not invite.get("winery_id"):
            cur.execute("SELECT id FROM wineries WHERE owner_user_id=%s FOR UPDATE",(user_id,)); owned=cur.fetchone()
            if not owned: raise HTTPException(409,"Completa prima la registrazione della cantina")
            invite["winery_id"]=owned["id"]
            cur.execute("UPDATE invites SET winery_id=%s WHERE id=%s",(owned["id"],invite["id"]))
        scope_type, scope_id = "winery", int(invite["winery_id"])
        if kind == "studio":
            cur.execute(
            """INSERT INTO studio_clients(studio_user_id,winery_id,can_view,can_edit,can_create,created_at)
               VALUES(%s,%s,%s,%s,%s,extract(epoch from now())::bigint)
               ON CONFLICT(studio_user_id,winery_id) DO UPDATE SET
                 can_view=excluded.can_view,can_edit=excluded.can_edit,can_create=excluded.can_create""",
                (user_id, scope_id, perms["can_view"], perms["can_edit"], perms["can_create"]),
            )
        elif kind == "winery":
            cur.execute("""INSERT INTO studio_clients(studio_user_id,winery_id,can_view,can_edit,can_create,created_at)
                VALUES(%s,%s,%s,%s,%s,extract(epoch from now())::bigint)
                ON CONFLICT(studio_user_id,winery_id) DO UPDATE SET can_view=excluded.can_view,
                can_edit=excluded.can_edit,can_create=excluded.can_create""",
                (invite["inviter_user_id"],scope_id,perms["can_view"],perms["can_edit"],perms["can_create"]))
    elif kind == "label":
        scope_type, scope_id = "label", int(invite["label_id"])
        cur.execute(
            """INSERT INTO label_collaborators(wine_label_id,collaborator_user_id,role,can_view,can_edit,
                 can_media,can_publish,can_export,commission_rate,active,created_at,updated_at)
               VALUES(%s,%s,'studio',%s,%s,%s,FALSE,%s,0,TRUE,now(),now())
               ON CONFLICT(wine_label_id,collaborator_user_id) WHERE active=TRUE DO UPDATE SET
                 can_view=excluded.can_view,can_edit=excluded.can_edit,can_media=excluded.can_media,
                 can_publish=FALSE,can_export=excluded.can_export,updated_at=now()""",
            (scope_id,user_id,perms["can_view"],perms["can_edit"],perms["can_edit"],perms["can_view"]),
        )
    else:
        scope_type, scope_id = "wine", int(invite["wine_id"])
    cur.execute(
        """INSERT INTO invitation_grants(invitation_id,user_id,scope_type,scope_id,permissions)
           VALUES(%s,%s,%s,%s,%s::jsonb)""",
        (invite["id"], user_id, scope_type, scope_id, json.dumps(perms)),
    )
    return scope_type, scope_id


def decide_invitation(*, raw: str, user: Mapping[str, Any], decision: str) -> dict[str, Any]:
    digest = validate_token(raw)
    return _decide(user=user, decision=decision, token_digest=digest)


def decide_invitation_by_id(*, invite_id: int, user: Mapping[str, Any], decision: str) -> dict[str, Any]:
    return _decide(user=user, decision=decision, invite_id=int(invite_id))


def _decide(*, user: Mapping[str, Any], decision: str,
            token_digest: str | None = None, invite_id: int | None = None) -> dict[str, Any]:
    if decision not in {"accept", "reject"}:
        raise HTTPException(422, "Decisione non valida")
    actor_id, email = int(user.get("id") or 0), str(user.get("email") or "").strip().lower()
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if invite_id is not None:
                cur.execute("SELECT * FROM invites WHERE id=%s FOR UPDATE", (invite_id,))
            else:
                cur.execute("SELECT * FROM invites WHERE token_hash=%s FOR UPDATE", (token_digest,))
            invite = cur.fetchone()
            if not invite: raise HTTPException(404, "Invito non valido")
            invite = dict(invite)
            if invite["status"] != "pending": raise HTTPException(409, f"Invito {invite['status']}")
            if invite["expires_at"] <= datetime.now(timezone.utc):
                cur.execute("UPDATE invites SET status='expired' WHERE id=%s", (invite["id"],)); conn.commit()
                raise HTTPException(410, "Invito scaduto")
            if email != str(invite["invitee_email"]).lower():
                raise HTTPException(403, "Accedi con l’indirizzo email destinatario dell’invito")
            cur.execute("SELECT email_verified,role FROM users WHERE id=%s",(actor_id,)); account=cur.fetchone()
            if not account or not int(account.get("email_verified") or 0):
                raise HTTPException(403,"Verifica l’indirizzo email prima di accettare")
            expected_role = str(invite.get("target_role") or "")
            if expected_role and str(account.get("role") or "") not in {expected_role,"admin"}:
                raise HTTPException(403,"Il ruolo dell’account non è compatibile con questo invito")
            if decision == "reject":
                cur.execute("UPDATE invites SET status='rejected',rejected_at=now() WHERE id=%s", (invite["id"],))
                _audit(cur,"invitation_rejected",actor_id,invite["id"]); conn.commit()
                return {**invite,"status":"rejected"}
            scope_type, scope_id = _grant(cur, invite, actor_id)
            cur.execute("""UPDATE invites SET status='accepted',accepted_at=now(),accepted_by_user_id=%s,
                           recipient_user_id=%s WHERE id=%s AND status='pending' RETURNING *""",
                        (actor_id,actor_id,invite["id"]))
            accepted = dict(cur.fetchone())
            _audit(cur,"invitation_accepted",actor_id,invite["id"],{"scope_type":scope_type,"scope_id":scope_id})
            cur.execute("SELECT 1 FROM invitation_grants WHERE invitation_id=%s AND user_id=%s AND active", (invite["id"],actor_id))
            if not cur.fetchone(): raise RuntimeError("Verifica grant invito fallita")
        conn.commit()
    return accepted


def revoke_or_resend(*, invite_id: int, actor: Mapping[str, Any], resend: bool = False) -> dict[str, Any]:
    actor_id = int(actor.get("id") or 0)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM invites WHERE id=%s FOR UPDATE", (invite_id,)); old = cur.fetchone()
            if not old or int(old["inviter_user_id"]) != actor_id: raise HTTPException(404,"Invito non trovato")
            if old["status"] == "accepted": raise HTTPException(409,"Un invito accettato non può essere reinviato")
            if old["status"] != "pending" and not resend: raise HTTPException(409,"Invito non revocabile")
            cur.execute("UPDATE invites SET status='revoked',revoked_at=now(),revoked_by_user_id=%s WHERE id=%s",(actor_id,invite_id))
            _audit(cur,"invitation_revoked",actor_id,invite_id)
        conn.commit()
    if not resend: return {"id":invite_id,"status":"revoked"}
    return create_invitation(invite_type=old["invite_type"], inviter=actor,
        recipient_email=old["invitee_email"], winery_id=old["winery_id"], wine_id=old["wine_id"],
        label_id=old["label_id"], studio_id=old["studio_id"], permissions=old["permissions_json"])


def revoke_invitation_access(*, invite_id: int, actor: Mapping[str, Any]) -> dict[str, Any]:
    actor_id=int(actor.get("id") or 0)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM invites WHERE id=%s FOR UPDATE",(invite_id,)); invite=cur.fetchone()
            if not invite or int(invite["inviter_user_id"])!=actor_id: raise HTTPException(404,"Invito non trovato")
            if invite["status"]!="accepted": raise HTTPException(409,"Accesso non attivo")
            cur.execute("UPDATE invitation_grants SET active=FALSE,revoked_at=now(),revoked_by_user_id=%s WHERE invitation_id=%s AND active RETURNING user_id,scope_type,scope_id",(actor_id,invite_id)); grants=cur.fetchall()
            for grant in grants:
                if grant["scope_type"]=="label":
                    cur.execute("UPDATE label_collaborators SET active=FALSE,can_view=FALSE,can_edit=FALSE,can_media=FALSE,can_publish=FALSE,can_export=FALSE,updated_at=now() WHERE wine_label_id=%s AND collaborator_user_id=%s AND active",(grant["scope_id"],grant["user_id"]))
                elif grant["scope_type"]=="winery" and invite["invite_type"]=="studio":
                    cur.execute("DELETE FROM studio_clients WHERE winery_id=%s AND studio_user_id=%s",(grant["scope_id"],grant["user_id"]))
            _audit(cur,"invitation_access_revoked",actor_id,invite_id,{"grant_count":len(grants)})
        conn.commit()
    return {"id":invite_id,"grants_revoked":len(grants)}
