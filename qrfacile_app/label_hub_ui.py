# /opt/qrfacile/qrfacile_app/label_hub_ui.py

import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.ui_shell import page, top_actions, esc, pill

router = APIRouter()


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))
    except Exception:
        return "-"


def _admin_active_winery_id(cur, user_id: int) -> int | None:
    cur.execute("SELECT admin_active_winery_id FROM users WHERE id=%s LIMIT 1", (int(user_id),))
    r = cur.fetchone() or {}
    wid = r.get("admin_active_winery_id")
    return int(wid) if wid else None


def _load_label(cur, label_id: int) -> dict:
    cur.execute(
        """
        SELECT
          wl.id AS label_id,
          wl.winery_id,
          wl.wine_id,
          wl.qr_item_id,
          wl.label_type,
          wl.language,
          wl.title_override,
          wl.lot_override,
          wl.public_enabled,
          wl.updated_at,
          wl.created_by_user_id,
          qw.wine_name,
          qw.vintage,
          qw.lot AS wine_lot,
          w.name AS winery_name,
          w.owner_user_id,
          qi.slug
        FROM wine_labels wl
        JOIN qr_wines qw ON qw.id = wl.wine_id
        JOIN wineries w ON w.id = wl.winery_id
        JOIN qr_items qi ON qi.id = wl.qr_item_id
        WHERE wl.id=%s
        LIMIT 1
        """,
        (int(label_id),),
    )
    r = cur.fetchone()
    if not r:
        raise HTTPException(404, "Etichetta non trovata")
    return r


def _studio_can_access_label(cur, studio_user_id: int, label_id: int, winery_id: int) -> bool:
    """
    Lo studio può aprire l'hub etichetta solo se:
    - è collegato alla cantina (studio_clients.can_view=TRUE)
    - ed è assegnato a questa etichetta con label_collaborators.active=TRUE e can_view=TRUE
    """
    cur.execute(
        """
        SELECT 1
        FROM studio_clients sc
        WHERE sc.studio_user_id=%s
          AND sc.winery_id=%s
          AND sc.can_view=TRUE
        LIMIT 1
        """,
        (int(studio_user_id), int(winery_id)),
    )
    if not cur.fetchone():
        return False

    cur.execute(
        """
        SELECT 1
        FROM label_collaborators lc
        WHERE lc.wine_label_id=%s
          AND lc.collaborator_user_id=%s
          AND lc.active=TRUE
          AND lc.can_view=TRUE
        LIMIT 1
        """,
        (int(label_id), int(studio_user_id)),
    )
    return bool(cur.fetchone())


def _connected_studios_for_label(cur, label_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
          lc.collaborator_user_id,
          lc.can_view,
          lc.can_edit,
          lc.can_media,
          lc.can_export,
          lc.can_publish,
          lc.active,
          u.email,
          COALESCE(s.company_name, '') AS company_name
        FROM label_collaborators lc
        JOIN users u ON u.id = lc.collaborator_user_id
        LEFT JOIN studios s ON s.user_id = u.id
        WHERE lc.wine_label_id=%s
          AND lc.active=TRUE
        ORDER BY lc.collaborator_user_id
        """,
        (int(label_id),),
    )
    return cur.fetchall() or []


def _columns(cur, table: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    return {r["column_name"] for r in (cur.fetchall() or [])}


def _pending_invites_for_label(cur, label_id: int) -> int:
    if "source_label_id" not in _columns(cur, "studio_invites"):
        return 0
    cur.execute(
        """
        SELECT COUNT(*)::int AS cnt
        FROM studio_invites
        WHERE source_label_id=%s
          AND used_at IS NULL
          AND (expires_at IS NULL OR expires_at >= EXTRACT(EPOCH FROM now())::bigint)
        """,
        (int(label_id),),
    )
    return int((cur.fetchone() or {}).get("cnt") or 0)


@router.get("/app/label/{label_id}", response_class=HTMLResponse)
def label_hub(request: Request, label_id: int):
    user = require_any_role(request, ("winery", "studio", "admin"))
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label(cur, int(label_id))

            # ======================
            # ACL
            # ======================
            if role == "winery":
                if int(label["owner_user_id"]) != uid:
                    raise HTTPException(403, "Forbidden")

            elif role == "admin":
                active_wid = _admin_active_winery_id(cur, uid)
                if not active_wid:
                    raise HTTPException(403, "Admin senza contesto cantina attivo")
                if int(active_wid) != int(label["winery_id"]):
                    raise HTTPException(403, "Contesto cantina non corrisponde all'etichetta")

            elif role == "studio":
                if not _studio_can_access_label(cur, uid, int(label_id), int(label["winery_id"])):
                    raise HTTPException(403, "Forbidden")

            assigned_studios = _connected_studios_for_label(cur, int(label_id))
            pending_invites = _pending_invites_for_label(cur, int(label_id))

    wine_name = esc(label.get("wine_name") or "")
    winery_name = esc(label.get("winery_name") or "")
    vintage = esc(label.get("vintage") or "")
    lot = esc(label.get("wine_lot") or "")
    slug = esc(label.get("slug") or "")
    updated = _fmt_ts(label.get("updated_at"))
    pub = bool(label.get("public_enabled"))

    badge_status = pill("Attiva", "green") if pub else pill("Bozza", "warn")
    pub_url = f"/e/{slug}" if slug else "#"

    # =========================
    # STUDIO BOX
    # =========================
    studio_box = ""

    if assigned_studios:
        cards = []
        for srow in assigned_studios:
            studio_name = (srow.get("company_name") or "").strip() or (srow.get("email") or "Studio")
            perms = []
            if srow.get("can_view"):
                perms.append("view")
            if srow.get("can_edit"):
                perms.append("edit")
            if srow.get("can_media"):
                perms.append("media")
            if srow.get("can_export"):
                perms.append("export")
            if srow.get("can_publish"):
                perms.append("publish")

            cards.append(f"""
            <div class="card" style="margin-top:10px">
              <div class="h2">{esc(studio_name)}</div>
              <div class="p" style="margin-top:6px">
                Permessi: <span class="mono">{esc(", ".join(perms) if perms else "-")}</span>
              </div>
            </div>
            """)

        studio_box = f"""
        <div class="card" style="margin-top:14px;border-left:4px solid rgba(34,197,94,.55)">
          <div class="h2">Chi lavora su questa etichetta?</div>
          <div class="p">
            <span class="pill pill-green">Studio assegnato</span><br>
            Questa etichetta è assegnata agli studi grafici operativi indicati sotto.
            La pubblicazione resta sotto controllo della cantina o dell’admin.
          </div>
          {''.join(cards)}
          {f"<div style='margin-top:12px'><a class='btn' href='/app/label/{int(label_id)}/acl'>Cambia Studio</a></div>" if role in ('winery', 'admin') else ""}
        </div>
        """
    elif pending_invites > 0 and role in ("winery", "admin"):
        studio_box = f"""
        <div class="card" style="margin-top:14px;border-left:4px solid rgba(245,158,11,.55)">
          <div class="h2">Chi lavora su questa etichetta?</div>
          <div class="p">
            <span class="pill pill-warn">Invito in attesa</span><br>
            Hai invitato uno Studio Grafico per questa etichetta. Lo studio apparirà qui dopo l'accettazione.
          </div>
          <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap">
            <a class="btn" href="/app/label/{int(label_id)}/acl">Cambia Studio</a>
            <a class="btn" href="/app/winery/settings">Inviti e studi</a>
          </div>
        </div>
        """
    elif role in ("winery", "admin"):
        studio_box = f"""
        <div class="card" style="margin-top:14px">
          <div class="h2">Chi lavora su questa etichetta?</div>
          <div class="p">
            <span class="pill pill-muted">Gestisco io</span><br>
            Nessuno studio grafico è ancora assegnato a questa etichetta.
            Puoi scegliere uno studio collegato alla cantina per seguirla operativamente.
          </div>
          <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap">
            <a class="btn btn-primary" href="/app/label/{int(label_id)}/acl">Assegna Studio</a>
            <a class="btn" href="/app/winery/settings">Studi grafici autorizzati</a>
          </div>
        </div>
        """

    # ======================
    # AZIONI HEADER
    # ======================
    actions = top_actions(
        (f"/app/wine/{int(label['wine_id'])}", "← Vino"),
        ("/app/dashboard", "Dashboard"),
        ("/app/labels/search", "Ricerca"),
        ("/logout", "Logout"),
    )

    # ======================
    # BODY
    # ======================
    open_public_btn = f"<a class='btn btn-primary' target='_blank' href='{pub_url}'>Apri pubblica</a>" if pub else ""

    studio_context_banner = ""
    if role == "studio":
        studio_context_banner = f"""
        <div class="card" style="margin-top:14px;border-left:4px solid rgba(59,130,246,.55);background:linear-gradient(135deg,rgba(239,246,255,.92),rgba(236,253,245,.88))">
          <div class="h2">Accesso Studio Grafico</div>
          <div class="p" style="margin-top:8px">
            Stai lavorando come <b>studio grafico</b> per la cantina:
            <b>{winery_name}</b>.<br>
            La pubblicazione e la gestione proprietaria restano alla cantina.
          </div>
        </div>
        """

    body = f"""
    {studio_context_banner}

    <div class="h1" style="margin-top:14px">
      Etichetta #{int(label_id)} {badge_status}
    </div>

    <div class="p">
      {winery_name} · {wine_name} {("· " + vintage) if vintage else ""}
    </div>

    <div class="note" style="margin-top:12px">
      Lotto: <b>{lot or "-"}</b> · Slug: <span class="mono">{slug or "-"}</span> · Aggiornata: {updated}
    </div>

    <div class="card" style="margin-top:14px">
      <div style="display:flex;gap:10px;flex-wrap:wrap">
        <a class="btn" href="/app/wine/{int(label['wine_id'])}/images">Immagini</a>
        <a class="btn" href="/app/wine/{int(label['wine_id'])}/compliance">Compliance</a>
        <a class="btn" href="/app/label/{int(label_id)}/history">Storico</a>
        {'' if role == 'studio' else f'<a class="btn" href="/app/label/{int(label_id)}/acl">Studio assegnato</a>'}
        {open_public_btn}
      </div>

      {"<div class='note' style='margin-top:12px'>Non pubblicata: resta in bozza finché non la attivi.</div>" if not pub else ""}
    </div>

    {studio_box}

    <div class="note" style="margin-top:16px">
      Flusso consigliato: <b>Immagine → Compliance → Export</b>.
      La pubblicazione è gestita da Cantina/Admin.
    </div>
    """

    return HTMLResponse(
        page(
            title="QRFACILE",
            subtitle="Etichetta",
            body_html=body,
            actions_html=actions,
            user_email=user.get("email", ""),
            role=role,
            credits=None,
        )
    )
