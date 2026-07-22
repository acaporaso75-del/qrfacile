import io
import re
import zipfile

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.auth_core import require_any_role, studio_allowed_wineries, winery_id_for_owner
from qrfacile_app.ui_shell import page, top_actions, esc, pill

# QR
import qrcode
from PIL import Image
try:
    import segno
except Exception:
    segno = None

router = APIRouter()


def _sanitize_filename(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:140] if s else "file"


def _qr_url(request: Request, slug: str) -> str:
    base = getattr(request.app.state, "app_base_url", "").rstrip("/")
    if not base:
        base = f"{request.url.scheme}://{request.headers.get('host','localhost:8000')}"
    return f"{base}/e/{slug}"


def _qr_png(url: str) -> bytes:
    if segno:
        qr = segno.make(url, micro=False)
        bio = io.BytesIO()
        qr.save(bio, kind="png", scale=10, border=4)
        return bio.getvalue()
    img = qrcode.make(url)
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def _qr_jpg(url: str) -> bytes:
    png = _qr_png(url)
    img = Image.open(io.BytesIO(png))
    if img.mode != "RGB":
        img = img.convert("RGB")
    bio = io.BytesIO()
    img.save(bio, format="JPEG", quality=92, optimize=True, progressive=True)
    return bio.getvalue()


def _qr_svg(url: str) -> bytes:
    if not segno:
        raise HTTPException(501, "SVG non disponibile: installa segno")
    qr = segno.make(url, micro=False)
    bio = io.BytesIO()
    qr.save(bio, kind="svg", border=4, xmldecl=True)
    return bio.getvalue()


def _admin_active_winery_id(cur, user_id: int) -> int | None:
    cur.execute("SELECT admin_active_winery_id FROM users WHERE id=%s LIMIT 1", (int(user_id),))
    r = cur.fetchone() or {}
    wid = r.get("admin_active_winery_id")
    return int(wid) if wid else None


def _allowed_wineries(cur, user: dict) -> list[int]:
    role = (user.get("role") or "").lower().strip()

    if role == "admin":
        active = _admin_active_winery_id(cur, int(user["id"]))
        return [active] if active else []

    if role == "studio":
        return studio_allowed_wineries(int(user["id"]), need="view")

    wid = winery_id_for_owner(int(user["id"]))
    return [wid] if wid else []


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


def _worker_badge_html(r: dict, role: str) -> str:
    assigned_count = int(r.get("assigned_count") or 0)
    pending_count = int(r.get("pending_invite_count") or 0)
    names = (r.get("assigned_studio_names") or "").strip()

    if pending_count > 0:
        tone = "pending"
        label = "Invito in attesa"
    elif assigned_count > 0:
        tone = "assigned"
        label = f"Studio assegnato: {names}" if names else "Studio assegnato"
    else:
        tone = "self"
        label = "Gestisco io"

    label_id = int(r["label_id"])
    action = ""
    if role in ("winery", "admin"):
        action = f'<a class="labelManagementAction" href="/app/label/{label_id}/acl">Cambia gestione</a>'

    return f"""
    <div class="labelManagement labelManagement-{tone}">
      <span>Gestione:</span>
      <b>{esc(label)}</b>
      {action}
    </div>
    """


@router.get("/app/labels/search", response_class=HTMLResponse)
def labels_search(request: Request, q: str = "", f: str = "all", winery_id: int = 0, work: str = "all"):
    user = require_any_role(request, ("winery", "studio", "admin"))
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            allowed = _allowed_wineries(cur, user)

            if not allowed:
                if role == "admin":
                    return HTMLResponse(page(
                        title="QRFACILE · Ricerca etichette",
                        subtitle="Ricerca etichette",
                        body_html="""
                        <div class="card" style="margin-top:14px">
                          <div class="h2">Seleziona una cantina</div>
                          <div class="p">Come admin lavori in contesto cantina. Vai su Admin e imposta prima la cantina attiva.</div>
                          <div style="margin-top:14px">
                            <a class="btn btn-primary" href="/admin">Apri Admin</a>
                          </div>
                        </div>
                        """,
                        actions_html=top_actions(("/admin", "Admin"), ("/logout", "Logout")),
                        user_email=user.get("email", ""),
                        role=role,
                        credits=None,
                    ))
                return HTMLResponse(page(
                    title="QRFACILE · Ricerca etichette",
                    subtitle="Ricerca etichette",
                    body_html="""
                    <div class="card" style="margin-top:14px">
                      <div class="h2">Nessuna cantina disponibile</div>
                      <div class="p">Non risultano cantine accessibili con il tuo account.</div>
                    </div>
                    """,
                    actions_html=top_actions(("/app/dashboard", "Dashboard"), ("/logout", "Logout")),
                    user_email=user.get("email", ""),
                    role=role,
                    credits=None,
                ))

            wid = int(winery_id or 0)
            if wid and wid not in allowed:
                wid = 0

            if role == "admin":
                # admin lavora solo sulla cantina attiva
                wid = allowed[0]

            cur.execute(
                """
                SELECT id, name
                FROM wineries
                WHERE id = ANY(%s)
                ORDER BY lower(name)
                """,
                (allowed,),
            )
            wineries = cur.fetchall() or []

            where = []
            params = []
            work = (work or "all").strip().lower()
            if work not in ("all", "self", "assigned", "pending"):
                work = "all"

            # scope base per ruolo
            if role == "studio":
                where.append("""
                    wl.id IN (
                        SELECT lc.wine_label_id
                        FROM label_collaborators lc
                        WHERE lc.collaborator_user_id=%s
                          AND lc.active=TRUE
                          AND lc.can_view=TRUE
                    )
                """)
                params.append(uid)

                where.append("wl.winery_id = ANY(%s)")
                params.append(allowed)

            else:
                where.append("wl.winery_id = ANY(%s)")
                params.append(allowed)

            if wid:
                where.append("wl.winery_id=%s")
                params.append(wid)

            if f == "draft":
                where.append("wl.public_enabled=FALSE")
            elif f == "active":
                where.append("wl.public_enabled=TRUE")

            assigned_exists = """
                EXISTS (
                    SELECT 1
                    FROM label_collaborators lc_w
                    WHERE lc_w.wine_label_id = wl.id
                      AND lc_w.active = TRUE
                      AND lc_w.can_view = TRUE
                )
            """

            invite_cols = _columns(cur, "studio_invites")
            has_source_label = "source_label_id" in invite_cols
            pending_select = "0::int AS pending_invite_count"
            pending_join = ""
            pending_exists = "FALSE"
            if has_source_label:
                pending_select = "COALESCE(pinv.pending_invite_count, 0) AS pending_invite_count"
                pending_join = """
              LEFT JOIN LATERAL (
                SELECT COUNT(*)::int AS pending_invite_count
                FROM studio_invites si
                WHERE si.source_label_id = wl.id
                  AND si.used_at IS NULL
                  AND (si.expires_at IS NULL OR si.expires_at >= EXTRACT(EPOCH FROM now())::bigint)
              ) pinv ON TRUE
                """
                pending_exists = """
                EXISTS (
                    SELECT 1
                    FROM studio_invites si
                    WHERE si.source_label_id = wl.id
                      AND si.used_at IS NULL
                      AND (si.expires_at IS NULL OR si.expires_at >= EXTRACT(EPOCH FROM now())::bigint)
                )
                """

            if work == "assigned":
                where.append(assigned_exists)
            elif work == "pending":
                where.append(pending_exists)
            elif work == "self":
                where.append(f"NOT {assigned_exists} AND NOT {pending_exists}")

            qq = (q or "").strip()
            if qq:
                where.append("""
                    (
                        lower(qw.wine_name) LIKE %s
                        OR lower(COALESCE(qw.lot,'')) LIKE %s
                        OR lower(w.name) LIKE %s
                        OR lower(COALESCE(wl.title_override,'')) LIKE %s
                    )
                """)
                like = f"%{qq.lower()}%"
                params.extend([like, like, like, like])

            sql = f"""
              SELECT
                 wl.id AS label_id,
                 wl.public_enabled,
                 wl.label_type,
                 wl.language,
                 wl.updated_at,
                 wl.title_override,
                 qw.id AS wine_id,
                 qw.wine_name,
                 qw.vintage,
                 qw.lot,
                 w.id AS winery_id,
                 w.name AS winery_name,
                 COALESCE(lca.assigned_count, 0) AS assigned_count,
                 COALESCE(lca.assigned_studio_names, '') AS assigned_studio_names,
                 {pending_select}
              FROM wine_labels wl
              JOIN qr_wines qw ON qw.id = wl.wine_id
              JOIN wineries w ON w.id = wl.winery_id
              LEFT JOIN LATERAL (
                SELECT
                  COUNT(*)::int AS assigned_count,
                  STRING_AGG(DISTINCT COALESCE(NULLIF(s.company_name, ''), u.email), ', ') AS assigned_studio_names
                FROM label_collaborators lc
                JOIN users u ON u.id = lc.collaborator_user_id
                LEFT JOIN studios s ON s.user_id = u.id
                WHERE lc.wine_label_id = wl.id
                  AND lc.active=TRUE
                  AND lc.can_view=TRUE
              ) lca ON TRUE
              {pending_join}
              WHERE {" AND ".join(where)}
              ORDER BY wl.updated_at DESC, wl.id DESC
              LIMIT 200
            """
            cur.execute(sql, tuple(params))
            rows = cur.fetchall() or []

    # dropdown cantine
    if role == "admin":
        opts = [
            f"<option value='{int(w['id'])}' selected>{esc(w['name'])}</option>"
            for w in wineries
        ]
    else:
        opts = ["<option value='0'>Tutte le cantine</option>"] + [
            f"<option value='{int(w['id'])}' {'selected' if int(w['id']) == int(winery_id or 0) else ''}>{esc(w['name'])}</option>"
            for w in wineries
        ]

    actions = top_actions(
        ("/app/dashboard", "Dashboard"),
        ("/app/winery/settings", "Studi"),
        ("/logout", "Logout"),
    )

    if role == "studio":
        actions += " " + top_actions(("/studio", "Studio"))
    if role == "admin":
        actions += " " + top_actions(("/admin", "Admin"))

    filters = f"""
    <form method="get" action="/app/labels/search" class="card" style="margin-top:14px">
      <div class="row" style="gap:10px;flex-wrap:wrap;align-items:flex-end">
        <div style="min-width:220px;flex:1">
          <label>Cerca</label>
          <input class="input" name="q" value="{esc(q)}" placeholder="vino, lotto, cantina, titolo">
        </div>

        <div style="min-width:220px">
          <label>Cantina</label>
          <select name="winery_id" {"disabled" if role == "admin" else ""}>
            {''.join(opts)}
          </select>
          {f"<input type='hidden' name='winery_id' value='{int(wid or 0)}'>" if role == 'admin' else ""}
        </div>

        <div style="min-width:180px">
          <label>Stato</label>
          <select name="f">
            <option value="all" {'selected' if f=='all' else ''}>Tutte</option>
            <option value="draft" {'selected' if f=='draft' else ''}>Bozze</option>
            <option value="active" {'selected' if f=='active' else ''}>Pubblicate</option>
          </select>
        </div>

        <div style="min-width:210px">
          <label>Chi lavora</label>
          <select name="work">
            <option value="all" {'selected' if work=='all' else ''}>Tutte</option>
            <option value="self" {'selected' if work=='self' else ''}>Gestisco io</option>
            <option value="assigned" {'selected' if work=='assigned' else ''}>Studio assegnato</option>
            <option value="pending" {'selected' if work=='pending' else ''}>Invito in attesa</option>
          </select>
        </div>

        <button class="btn btn-primary" type="submit">Cerca</button>
      </div>
    </form>
    """

    def row_card(r: dict) -> str:
        label_id = int(r["label_id"])
        wine_id = int(r["wine_id"])
        wine_name = r.get("wine_name") or "-"
        lot = r.get("lot") or ""
        winery_name = r.get("winery_name") or "-"
        title_override = r.get("title_override") or ""
        label_type = r.get("label_type") or ""
        language = r.get("language") or ""
        pub = bool(r.get("public_enabled"))
        state_pill = "pill pill-green" if pub else "pill pill-muted"
        st = "PUBBLICA" if pub else "BOZZA"
        worker_html = _worker_badge_html(r, role)

        meta_parts = [winery_name]
        if lot:
            meta_parts.append(f"Lotto: {lot}")
        if label_type:
            meta_parts.append(f"Tipo: {label_type}")
        if language:
            meta_parts.append(f"Lingua: {language}")
        if title_override:
            meta_parts.append(title_override)

        return f"""
        <div class="card" style="margin-top:12px">
          <div style="display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap">
            <div class="left" style="min-width:0;flex:1">
              <div class="title" style="font-weight:950">{esc(wine_name)} <span class="{state_pill}">{st}</span></div>
              <div class="meta" style="margin-top:6px;color:var(--muted)">{esc(' · '.join(meta_parts))}</div>
              {worker_html}
            </div>
            <div class="actions" style="display:flex;gap:10px;flex-wrap:wrap">
              <a class="btn" href="/app/wine/{wine_id}">Apri vino</a>
              <a class="btn btn-primary" href="/app/label/{label_id}">Apri etichetta</a>
            </div>
          </div>
        </div>
        """

    cards = "".join(row_card(r) for r in rows) if rows else """
    <div class="card" style="margin-top:12px">
      <div class="h2">Nessun risultato</div>
      <div class="p">Prova a cambiare filtri o ricerca.</div>
    </div>
    """

    intro = "Filtra per cantina e cerca per vino, lotto o titolo."
    if role == "studio":
        intro = "Vedi solo le etichette assegnate al tuo studio."
    elif role == "admin":
        intro = "Stai lavorando nel contesto della cantina attiva."

    body = f"""
    <div class="h1" style="margin-top:14px">Ricerca etichette</div>
    <div class="p">{esc(intro)}</div>

    {filters}

    <div style="margin-top:14px;display:flex;flex-direction:column;gap:12px">
      {cards}
    </div>

    <style>
      .labelManagement {{
        margin-top:10px;
        display:inline-flex;
        align-items:center;
        gap:8px;
      }}
      .labelManagement > span {{
        color:#64748b;
        font-weight:900;
      }}
      .labelManagement b,
      .labelManagementAction {{
        display:inline-flex;
        align-items:center;
        max-width:220px;
        padding:5px 9px;
        border-radius:999px;
        background:rgba(248,250,252,.92);
        color:#0f172a;
        font-weight:950;
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
        cursor:pointer;
        list-style:none;
      }}
      .labelManagement-assigned b {{
        background:rgba(236,253,245,.88);
        color:#0f766e;
      }}
      .labelManagement-pending b {{
        background:rgba(255,251,235,.92);
        color:#92400e;
      }}
      .labelManagementAction {{
        background:white;
        box-shadow:inset 0 0 0 1px rgba(2,8,23,.08);
      }}
    </style>
    """

    return HTMLResponse(page(
        title="QRFACILE · Ricerca etichette",
        subtitle="Ricerca etichette",
        body_html=body,
        actions_html=actions,
        user_email=user.get("email", ""),
        role=role,
        credits=None,
    ))


@router.get("/app/labels/export-zip")
def labels_export_zip(request: Request, ids: str = ""):
    """
    Export ZIP QR di più etichette.
    Per ora mantenuto semplice e sicuro:
    - winery/admin: possono esportare solo etichette nel loro scope
    - studio: solo etichette assegnate e con accesso view
    """
    user = require_any_role(request, ("winery", "studio", "admin"))
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    raw_ids = [x.strip() for x in (ids or "").split(",") if x.strip()]
    try:
        label_ids = [int(x) for x in raw_ids][:100]
    except Exception:
        raise HTTPException(400, "IDs non validi")

    if not label_ids:
        raise HTTPException(400, "Nessuna etichetta selezionata")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            allowed = _allowed_wineries(cur, user)
            if not allowed:
                raise HTTPException(403, "Forbidden")

            if role == "studio":
                cur.execute(
                    """
                    SELECT wl.id, qi.slug, qw.wine_name
                    FROM wine_labels wl
                    JOIN qr_items qi ON qi.id = wl.qr_item_id
                    JOIN qr_wines qw ON qw.id = wl.wine_id
                    JOIN label_collaborators lc ON lc.wine_label_id = wl.id
                    WHERE wl.id = ANY(%s)
                      AND wl.winery_id = ANY(%s)
                      AND lc.collaborator_user_id=%s
                      AND lc.active=TRUE
                      AND lc.can_view=TRUE
                    ORDER BY wl.id
                    """,
                    (label_ids, allowed, uid),
                )
            else:
                cur.execute(
                    """
                    SELECT wl.id, qi.slug, qw.wine_name
                    FROM wine_labels wl
                    JOIN qr_items qi ON qi.id = wl.qr_item_id
                    JOIN qr_wines qw ON qw.id = wl.wine_id
                    WHERE wl.id = ANY(%s)
                      AND wl.winery_id = ANY(%s)
                    ORDER BY wl.id
                    """,
                    (label_ids, allowed),
                )

            rows = cur.fetchall() or []

    if not rows:
        raise HTTPException(404, "Nessuna etichetta esportabile")

    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for r in rows:
            slug = (r.get("slug") or "").strip()
            if not slug:
                continue
            wine_name = _sanitize_filename(r.get("wine_name") or f"label_{r['id']}")
            url = _qr_url(request, slug)
            zf.writestr(f"{wine_name}_{int(r['id'])}.png", _qr_png(url))

    mem.seek(0)
    return StreamingResponse(
        mem,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="labels_qr_bundle.zip"'},
    )
