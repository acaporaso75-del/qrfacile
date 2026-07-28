from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping

from fastapi import HTTPException
from psycopg.rows import dict_row

from qrfacile_app.db import pg


@dataclass(frozen=True)
class EffectiveLabelPermission:
    winery_id: int
    wine_id: int
    label_id: int
    can_view: bool
    can_edit: bool
    can_media: bool
    can_export: bool
    can_publish: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _role(user: Mapping[str, Any]) -> str:
    return str(user.get("role") or "").strip().lower()


def _user_id(user: Mapping[str, Any]) -> int:
    return int(user.get("id") or user.get("user_id") or 0)


def get_label_permission(user: Mapping[str, Any], label_id: int) -> EffectiveLabelPermission:
    role = _role(user)
    uid = _user_id(user)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT wl.id AS label_id, wl.winery_id, wl.wine_id, w.owner_user_id
                FROM wine_labels wl
                JOIN wineries w ON w.id=wl.winery_id
                WHERE wl.id=%s
                LIMIT 1
                """,
                (int(label_id),),
            )
            label = cur.fetchone()
            if not label:
                raise HTTPException(404, "Etichetta non trovata")

            if role == "admin" or (role == "winery" and uid == int(label.get("owner_user_id") or 0)):
                return EffectiveLabelPermission(
                    winery_id=int(label["winery_id"]), wine_id=int(label["wine_id"]),
                    label_id=int(label["label_id"]), can_view=True, can_edit=True,
                    can_media=True, can_export=True, can_publish=True,
                )

            if role != "studio":
                raise HTTPException(403, "Accesso negato")

            cur.execute(
                """
                SELECT
                    sc.can_view AS general_view,
                    sc.can_edit AS general_edit,
                    lc.can_view AS label_view,
                    lc.can_edit AS label_edit,
                    lc.can_media,
                    lc.can_export,
                    lc.active
                FROM studio_clients sc
                JOIN label_collaborators lc
                  ON lc.collaborator_user_id=sc.studio_user_id
                 AND lc.wine_label_id=%s
                WHERE sc.studio_user_id=%s
                  AND sc.winery_id=%s
                  AND lc.active=TRUE
                LIMIT 1
                """,
                (int(label_id), uid, int(label["winery_id"])),
            )
            permission = cur.fetchone()
            if not permission:
                raise HTTPException(403, "Etichetta non assegnata a questo studio")

            can_view = bool(permission.get("general_view") and permission.get("label_view"))
            can_edit = bool(can_view and permission.get("general_edit") and permission.get("label_edit"))
            if not can_view:
                raise HTTPException(403, "Accesso in sola cantina insufficiente: serve assegnazione esplicita dell'etichetta")

            return EffectiveLabelPermission(
                winery_id=int(label["winery_id"]), wine_id=int(label["wine_id"]),
                label_id=int(label["label_id"]), can_view=can_view, can_edit=can_edit,
                can_media=bool(can_edit and permission.get("can_media")),
                can_export=bool(can_view and permission.get("can_export")),
                can_publish=False,
            )


def require_label_permission(user: Mapping[str, Any], label_id: int, permission: str = "view") -> EffectiveLabelPermission:
    effective = get_label_permission(user, label_id)
    allowed = {
        "view": effective.can_view,
        "edit": effective.can_edit,
        "media": effective.can_media,
        "export": effective.can_export,
        "publish": effective.can_publish,
    }
    if permission not in allowed:
        raise ValueError(f"Permesso sconosciuto: {permission}")
    if not allowed[permission]:
        raise HTTPException(403, f"Permesso {permission} non concesso")
    return effective


def require_wine_access(user: Mapping[str, Any], wine_id: int, permission: str = "view") -> dict[str, Any]:
    role = _role(user)
    uid = _user_id(user)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT qw.id AS wine_id, qw.winery_id, w.owner_user_id
                FROM qr_wines qw JOIN wineries w ON w.id=qw.winery_id
                WHERE qw.id=%s LIMIT 1
                """,
                (int(wine_id),),
            )
            wine = cur.fetchone()
            if not wine:
                raise HTTPException(404, "Vino non trovato")
            if role == "admin" or (role == "winery" and uid == int(wine.get("owner_user_id") or 0)):
                return dict(wine)
            if role != "studio":
                raise HTTPException(403, "Accesso negato")

            required_column = "lc.can_view" if permission == "view" else "lc.can_edit"
            cur.execute(
                f"""
                SELECT 1
                FROM wine_labels wl
                JOIN label_collaborators lc ON lc.wine_label_id=wl.id
                JOIN studio_clients sc
                  ON sc.studio_user_id=lc.collaborator_user_id
                 AND sc.winery_id=wl.winery_id
                WHERE wl.wine_id=%s
                  AND lc.collaborator_user_id=%s
                  AND lc.active=TRUE
                  AND lc.can_view=TRUE
                  AND sc.can_view=TRUE
                  AND {required_column}=TRUE
                  AND (%s='view' OR sc.can_edit=TRUE)
                LIMIT 1
                """,
                (int(wine_id), uid, permission),
            )
            if not cur.fetchone():
                raise HTTPException(403, "Nessuna etichetta del vino è stata assegnata allo studio con il permesso richiesto")
            return dict(wine)


def list_wine_access(user: Mapping[str, Any], wine_id: int) -> dict[str, Any]:
    wine = require_wine_access(user, wine_id, "view")
    role = _role(user)
    uid = _user_id(user)
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT wl.id AS label_id, wl.label_type, wl.language, wl.public_enabled,
                       lc.id AS collaboration_id, lc.collaborator_user_id,
                       COALESCE(s.company_name, u.email, '') AS studio_name,
                       u.email, lc.can_view, lc.can_edit, lc.can_media, lc.can_export,
                       lc.active, lc.created_at, lc.updated_at
                FROM wine_labels wl
                LEFT JOIN label_collaborators lc ON lc.wine_label_id=wl.id AND lc.active=TRUE
                LEFT JOIN users u ON u.id=lc.collaborator_user_id
                LEFT JOIN studios s ON s.user_id=lc.collaborator_user_id
                WHERE wl.wine_id=%s
                ORDER BY wl.id, lc.id
                """,
                (int(wine_id),),
            )
            rows = [dict(row) for row in cur.fetchall()]
    if role == "studio":
        rows = [row for row in rows if int(row.get("collaborator_user_id") or 0) == uid]
    return {"wine": wine, "labels": rows}
