import json
import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.auth import require_any_role
from qrfacile_app import ui

router = APIRouter()


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))
    except Exception:
        return "-"


def _load_label(cur, label_id: int) -> dict:
    cur.execute("""
      SELECT
        wl.id AS label_id,
        wl.winery_id,
        wl.wine_id,
        wl.label_type,
        wl.language,
        wl.public_enabled,
        wl.updated_at,
        qw.wine_name,
        w.name AS winery_name,
        w.owner_user_id
      FROM wine_labels wl
      JOIN qr_wines qw ON qw.id = wl.wine_id
      JOIN wineries w ON w.id = wl.winery_id
      WHERE wl.id=%s
      LIMIT 1
    """, (int(label_id),))
    r = cur.fetchone()
    if not r:
        raise HTTPException(404, "Etichetta non trovata")
    return r


def _studio_acl(cur, studio_user_id: int, winery_id: int) -> dict | None:
    cur.execute("""
      SELECT can_view, can_edit, can_create
      FROM studio_clients
      WHERE studio_user_id=%s AND winery_id=%s
      LIMIT 1
    """, (int(studio_user_id), int(winery_id)))
    return cur.fetchone()


def _can_view(user: dict, label: dict, cur) -> bool:
    role = (user.get("role") or "").lower().strip()
    if role == "admin":
        return True
    if role == "winery":
        return int(label["owner_user_id"]) == int(user["id"])
    if role == "studio":
        acl = _studio_acl(cur, int(user["id"]), int(label["winery_id"]))
        return bool(acl and acl.get("can_view"))
    return False


def _can_edit(user: dict, label: dict, cur) -> bool:
    role = (user.get("role") or "").lower().strip()
    if role == "admin":
        return True
    if role == "winery":
        return int(label["owner_user_id"]) == int(user["id"])
    if role == "studio":
        acl = _studio_acl(cur, int(user["id"]), int(label["winery_id"]))
        return bool(acl and acl.get("can_edit"))
    return False


@router.get("/app/label/{label_id}/history", response_class=HTMLResponse)
def label_history_page(request: Request, label_id: int, msg: str = ""):
    user = require_any_role(request, ("winery", "studio", "admin"))
    role = (user.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label(cur, int(label_id))
            if not _can_view(user, label, cur):
                raise HTTPException(403, "Forbidden")

            cur.execute("""
              SELECT id, created_at, actor_user_id
              FROM wine_label_history
              WHERE wine_label_id=%s
              ORDER BY created_at DESC
              LIMIT 80
            """, (int(label_id),))
            rows = cur.fetchall() or []

            actor_map = {}
            actor_ids = [r["actor_user_id"] for r in rows if r.get("actor_user_id")]
            if actor_ids:
                cur.execute("""
                  SELECT id, email, role
                  FROM users
                  WHERE id = ANY(%s)
                """, (actor_ids,))
                for u in (cur.fetchall() or []):
                    actor_map[int(u["id"])] = u

    msg_html = f"<div class='note'><b>OK:</b> {ui.esc(msg)}</div>" if msg else ""

    def row_html(r: dict) -> str:
        hid = int(r["id"])
        ts = _fmt_ts(int(r.get("created_at") or 0))
        actor = "-"
        if r.get("actor_user_id"):
            au = actor_map.get(int(r["actor_user_id"]))
            if au:
                actor = f'{au.get("email","-")} ({au.get("role","-")})'
        return f"""
        <div class="rowCard">
          <div class="left">
            <div class="title">Snapshot #{hid}</div>
            <div class="meta">{ui.esc(ts)} · {ui.esc(actor)}</div>
          </div>
          <div class="actions">
            <a class="btn" href="/app/label/{int(label_id)}/rollback/{hid}">Rollback</a>
          </div>
        </div>
        """

    rows_html = "".join(row_html(r) for r in rows) if rows else (
        "<div class='card'><b>Nessuno storico</b><div class='muted'>Ancora nessun salvataggio registrato.</div></div>"
    )

    html = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Storico etichetta #{int(label_id)}</title>
<link rel="stylesheet" href="/static/app.css">
<style>
.rowCard{{display:flex;justify-content:space-between;gap:14px;align-items:center;padding:14px;border-radius:18px;border:1px solid var(--line);background:rgba(255,255,255,.92)}}
.rowCard:hover{{box-shadow:var(--shadow);border-color:rgba(34,197,94,.35)}}
.left{{min-width:0;flex:1}}
.title{{font-weight:950;letter-spacing:-.2px}}
.meta{{margin-top:6px;color:var(--muted);font-size:13px;font-weight:650;line-height:1.4}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:flex-end}}
</style>
</head>
<body>
<div class="container">
  <div class="topbar">
    <div class="brand">
      <div class="brand-dot"></div>
      <div>
        <div class="brand-title">QRFACILE</div>
        <div class="brand-sub">Etichetta · Storico</div>
      </div>
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <a class="pill" href="/app/label/{int(label_id)}">← Etichetta</a>
      <a class="pill" href="/app/labels/search">Ricerca avanzata</a>
      <a class="pill" href="/logout">Logout</a>
    </div>
  </div>

  <div class="h1">Storico etichetta #{int(label_id)}</div>
  <div class="p">{ui.esc(label.get("winery_name") or "-")} · {ui.esc(label.get("wine_name") or "-")}</div>

  {msg_html}

  <div style="display:flex;flex-direction:column;gap:12px;margin-top:14px">
    {rows_html}
  </div>

  <div class="note" style="margin-top:16px">
    Rollback: ripristina lo snapshot sul record etichetta (funzione base).
  </div>
</div>
</body>
</html>
"""
    return HTMLResponse(html)


@router.get("/app/label/{label_id}/rollback/{history_id}")
def label_rollback(request: Request, label_id: int, history_id: int):
    user = require_any_role(request, ("winery", "studio", "admin"))

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label(cur, int(label_id))
            if not _can_edit(user, label, cur):
                raise HTTPException(403, "Forbidden")

            cur.execute("""
              SELECT snapshot
              FROM wine_label_history
              WHERE id=%s AND wine_label_id=%s
              LIMIT 1
            """, (int(history_id), int(label_id)))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Snapshot non trovato")

            snap = row.get("snapshot") or {}
            if isinstance(snap, str):
                try:
                    snap = json.loads(snap)
                except Exception:
                    snap = {}

            # ripristino base su wine_labels (campi principali)
            ts = int(time.time())
            cur.execute("""
              UPDATE wine_labels
              SET
                title_override = %s,
                lot_override = %s,
                public_enabled = %s,
                updated_at = %s
              WHERE id=%s
            """, (
                snap.get("title_override"),
                snap.get("lot_override"),
                bool(snap.get("public_enabled")) if "public_enabled" in snap else False,
                ts,
                int(label_id),
            ))
            conn.commit()

    return RedirectResponse(f"/app/label/{int(label_id)}/history?msg=Rollback%20eseguito", status_code=303)
