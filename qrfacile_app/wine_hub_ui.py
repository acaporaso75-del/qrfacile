import time
from urllib.parse import quote_plus

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.ui_shell import page, top_actions, pill, esc

router = APIRouter()


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(int(ts)))
    except Exception:
        return "-"


def _public_url(app_base: str, slug: str) -> str:
    base = (app_base or "").rstrip("/")
    return f"{base}/e/{slug}" if base and slug else ""


def _balances(cur, user_id: int) -> dict:
    cur.execute(
        """
        SELECT credit_type, COALESCE(SUM(delta),0) AS bal
        FROM credit_ledger
        WHERE user_id=%s
        GROUP BY credit_type
        """,
        (int(user_id),),
    )

    out = {"wine": 0, "generic": 0}

    for r in (cur.fetchall() or []):
        ct = (r.get("credit_type") or "").strip().lower()
        if ct:
            out[ct] = int(r.get("bal") or 0)

    return out


def _admin_active_winery_id(cur, user_id: int) -> int | None:
    cur.execute(
        "SELECT admin_active_winery_id FROM users WHERE id=%s LIMIT 1",
        (int(user_id),),
    )
    r = cur.fetchone() or {}
    wid = r.get("admin_active_winery_id")
    return int(wid) if wid else None


def _load_wine(cur, wine_id: int) -> dict:
    cur.execute(
        """
        SELECT
          qw.id AS wine_id,
          qw.winery_id,
          qw.qr_item_id,
          qw.wine_name,
          qw.vintage,
          qw.lot,
          qw.updated_at,
          qi.slug,
          w.name AS winery_name,
          w.owner_user_id
        FROM qr_wines qw
        JOIN qr_items qi ON qi.id = qw.qr_item_id
        JOIN wineries w ON w.id = qw.winery_id
        WHERE qw.id=%s
        LIMIT 1
        """,
        (int(wine_id),),
    )
    r = cur.fetchone()

    if not r:
        raise HTTPException(404, "Vino non trovato")

    return r


def _studio_can_access_wine(cur, studio_user_id: int, winery_id: int) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM studio_clients
        WHERE studio_user_id=%s
          AND winery_id=%s
          AND can_view=TRUE
        LIMIT 1
        """,
        (int(studio_user_id), int(winery_id)),
    )
    return bool(cur.fetchone())


def _wine_assets(cur, wine_id: int) -> dict:
    cur.execute(
        """
        SELECT kind, img_thumb, img_optimized, img_original
        FROM wine_assets
        WHERE wine_id=%s
        """,
        (int(wine_id),),
    )
    return {r["kind"]: r for r in (cur.fetchall() or [])}


def _labels_for_wine(cur, wine_id: int, role: str, user_id: int) -> list[dict]:
    """
    winery/admin: tutte le etichette del vino
    studio: solo etichette assegnate allo studio
    """
    if role == "studio":
        cur.execute(
            """
            SELECT
              wl.id AS label_id,
              wl.label_type,
              wl.language,
              wl.lot_override,
              wl.title_override,
              wl.public_enabled,
              wl.updated_at,
              qi.slug AS label_slug
            FROM label_collaborators lc
            JOIN wine_labels wl ON wl.id = lc.wine_label_id
            JOIN qr_items qi ON qi.id = wl.qr_item_id
            WHERE wl.wine_id=%s
              AND lc.collaborator_user_id=%s
              AND lc.active=TRUE
              AND lc.can_view=TRUE
            ORDER BY wl.id DESC
            LIMIT 80
            """,
            (int(wine_id), int(user_id)),
        )
        return cur.fetchall() or []

    cur.execute(
        """
        SELECT
          wl.id AS label_id,
          wl.label_type,
          wl.language,
          wl.lot_override,
          wl.title_override,
          wl.public_enabled,
          wl.updated_at,
          qi.slug AS label_slug
        FROM wine_labels wl
        JOIN qr_items qi ON qi.id = wl.qr_item_id
        WHERE wl.wine_id=%s
        ORDER BY wl.id DESC
        LIMIT 80
        """,
        (int(wine_id),),
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


def _label_management_map(cur, label_ids: list[int]) -> dict[int, dict]:
    if not label_ids:
        return {}

    out = {int(label_id): {"assigned": "", "active_studio_user_id": 0, "pending": 0} for label_id in label_ids}

    cur.execute(
        """
        SELECT
          lc.wine_label_id AS label_id,
          STRING_AGG(DISTINCT COALESCE(NULLIF(s.company_name, ''), u.email), ', ') AS studio_names,
          MIN(lc.collaborator_user_id)::int AS active_studio_user_id
        FROM label_collaborators lc
        JOIN users u ON u.id = lc.collaborator_user_id
        LEFT JOIN studios s ON s.user_id = u.id
        WHERE lc.wine_label_id = ANY(%s)
          AND lc.active=TRUE
          AND lc.can_view=TRUE
        GROUP BY lc.wine_label_id
        """,
        (label_ids,),
    )
    for row in cur.fetchall() or []:
        out[int(row["label_id"])]["assigned"] = (row.get("studio_names") or "").strip()
        out[int(row["label_id"])]["active_studio_user_id"] = int(row.get("active_studio_user_id") or 0)

    if "source_label_id" in _columns(cur, "studio_invites"):
        cur.execute(
            """
            SELECT source_label_id AS label_id, COUNT(*)::int AS pending_count
            FROM studio_invites
            WHERE source_label_id = ANY(%s)
              AND used_at IS NULL
              AND (expires_at IS NULL OR expires_at >= EXTRACT(EPOCH FROM now())::bigint)
            GROUP BY source_label_id
            """,
            (label_ids,),
        )
        for row in cur.fetchall() or []:
            out[int(row["label_id"])]["pending"] = int(row.get("pending_count") or 0)

    return out


def _connected_studio_count(cur, winery_id: int) -> int:
    cur.execute(
        """
        SELECT COUNT(*)::int AS cnt
        FROM studio_clients sc
        JOIN users u ON u.id = sc.studio_user_id
        WHERE sc.winery_id=%s
          AND lower(u.role)='studio'
          AND sc.can_view=TRUE
        """,
        (int(winery_id),),
    )
    return int((cur.fetchone() or {}).get("cnt") or 0)


def _connected_studios(cur, winery_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
          u.id AS studio_user_id,
          u.email,
          COALESCE(s.company_name, '') AS company_name
        FROM studio_clients sc
        JOIN users u ON u.id = sc.studio_user_id
        LEFT JOIN studios s ON s.user_id = u.id
        WHERE sc.winery_id=%s
          AND lower(u.role)='studio'
          AND sc.can_view=TRUE
        ORDER BY lower(COALESCE(NULLIF(s.company_name, ''), u.email))
        """,
        (int(winery_id),),
    )
    return cur.fetchall() or []


def _wine_management_active_id(management: dict[int, dict]) -> int:
    active_ids = {
        int(info.get("active_studio_user_id") or 0)
        for info in management.values()
        if int(info.get("active_studio_user_id") or 0) > 0
    }
    if management and len(active_ids) == 1 and all(int(info.get("active_studio_user_id") or 0) in active_ids for info in management.values()):
        return active_ids.pop()
    return 0


def _label_type_name(label_type: str) -> str:
    lt = (label_type or "").strip().lower()
    if lt == "front":
        return "Fronte"
    if lt == "back":
        return "Retro"
    return (label_type or "Altro").strip().capitalize()


def _management_picker(wine_id: int, active_studio_user_id: int, studios: list[dict], return_to: str) -> str:
    options = [f"<option value='self' {'selected' if active_studio_user_id <= 0 else ''}>Gestisco io</option>"]
    for studio in studios:
        sid = int(studio["studio_user_id"])
        studio_name = (studio.get("company_name") or studio.get("email") or f"Studio {sid}").strip()
        selected = "selected" if sid == active_studio_user_id else ""
        options.append(f"<option value='studio:{sid}' {selected}>{esc(studio_name)}</option>")
    options.append("<option value='invite'>+ Invita nuovo Studio</option>")

    return f"""
    <form method="post" action="/app/wine/{int(wine_id)}/management/set" class="wineHubManagementPicker">
      <input type="hidden" name="return_to" value="{esc(return_to)}">
      <label>Gestione grafica</label>
      <select name="management_value">
        {''.join(options)}
      </select>
      <button class="btn" type="submit">Salva</button>
    </form>
    """


def _management_section(labels: list[dict], management: dict[int, dict], role: str, wine_id: int, studios: list[dict]) -> str:
    main_picker = ""
    if role in ("winery", "admin") and labels:
        main_picker = _management_picker(
            int(wine_id),
            _wine_management_active_id(management),
            studios,
            f"/app/wine/{int(wine_id)}#gestione-grafica",
        )

    if not labels:
        rows_html = """
        <div class="wineHubManagementEmpty">
          Nessuna etichetta fronte/retro ancora creata per questo lotto.
        </div>
        """
    else:
        rows_html = """
        <div class="wineHubManagementEmpty">
          La scelta viene applicata a tutte le etichette tecniche del lotto.
        </div>
        """

    return f"""
    <div class="card wineHubManagementCard" id="gestione-grafica">
      <div class="wineHubCardHead">
        <div>
          <div class="wineHubSmallLabel">Fronte / Retro</div>
          <div class="h2">Gestione grafica del lotto</div>
          <div class="p" style="margin-top:4px">Scegli chi lavora sulla grafica di questo lotto.</div>
        </div>
      </div>
      {main_picker}
      <div class="wineHubManagementList">
        {rows_html}
      </div>
    </div>
    """


def _asset_card(kind: str, asset: dict | None, wine_id: int) -> str:
    label = "Fronte" if kind == "front" else "Retro"
    asset = asset or {}
    thumb = (asset.get("img_thumb") or "").strip()

    if thumb:
        media = f"""
        <div class="wineHubImageBox">
          <img src="/uploads/{esc(thumb)}" alt="{esc(label)}">
        </div>
        """
    else:
        media = f"""
        <div class="wineHubImagePlaceholder">
          <div class="wineHubImageIcon">🖼️</div>
          <b>{esc(label)}</b>
          <span>Nessuna immagine caricata</span>
        </div>
        """

    return f"""
    <div class="card wineHubAssetCard">
      <div class="wineHubCardHead">
        <div>
          <div class="wineHubSmallLabel">Immagine etichetta</div>
          <div class="h2">{esc(label)}</div>
        </div>
        <a class="btn" href="/app/wine/{int(wine_id)}/images">Gestisci</a>
      </div>

      {media}
    </div>
    """


def _label_row(r: dict, role: str = "") -> str:
    label_id = int(r["label_id"])
    lt = (r.get("label_type") or "").strip()
    lang = (r.get("language") or "").strip()
    lot_override = (r.get("lot_override") or "").strip()
    title_override = (r.get("title_override") or "").strip()
    pub = bool(r.get("public_enabled"))
    slug2 = (r.get("label_slug") or "").strip()

    status = "Pubblica" if pub else "Bozza"
    status_badge = pill(status, "green" if pub else "muted")

    meta_parts = []
    if lt:
        meta_parts.append(f"tipo {lt}")
    if lang:
        meta_parts.append(f"lingua {lang}")
    if lot_override:
        meta_parts.append(f"lotto {lot_override}")
    if title_override:
        meta_parts.append(title_override)

    meta = " · ".join(meta_parts) if meta_parts else "Etichetta senza dettagli aggiuntivi"

    public_btn = ""
    if pub and slug2:
        public_btn = f"""
        <a class="btn" href="/e/{esc(slug2)}" target="_blank">
          Apri pubblica
        </a>
        """

    return f"""
    <div class="wineHubLabelRow">
      <div>
        <div class="wineHubLabelTitle">
          Etichetta #{label_id}
          {status_badge}
        </div>
        <div class="wineHubLabelMeta">{esc(meta)}</div>
      </div>

      <div class="wineHubLabelActions">
        <a class="btn btn-primary" href="/app/label/{label_id}">Apri</a>
        {public_btn}
      </div>
    </div>
    """


def _safe_return_to(return_to: str, wine_id: int) -> str:
    return_to = (return_to or "").strip()
    if return_to.startswith("/app/") and not return_to.startswith("//"):
        return return_to
    return f"/app/wine/{int(wine_id)}#gestione-grafica"


def _with_notice(url: str, key: str, message: str) -> str:
    base, fragment = (url or "").split("#", 1) if "#" in (url or "") else (url, "")
    sep = "&" if "?" in base else "?"
    out = f"{base}{sep}{key}={quote_plus(message)}"
    if fragment:
        out = f"{out}#{fragment}"
    return out


def _wine_label_ids(cur, wine_id: int) -> list[int]:
    cur.execute(
        "SELECT id FROM wine_labels WHERE wine_id=%s ORDER BY id",
        (int(wine_id),),
    )
    return [int(r["id"]) for r in (cur.fetchall() or [])]


def _assign_wine_management(cur, wine: dict, label_ids: list[int], studio_user_id: int) -> str | None:
    cur.execute(
        """
        SELECT can_view, can_edit, can_create
        FROM studio_clients
        WHERE winery_id=%s
          AND studio_user_id=%s
          AND can_view=TRUE
        LIMIT 1
        """,
        (int(wine["winery_id"]), int(studio_user_id)),
    )
    sc = cur.fetchone()
    if not sc:
        return "Studio non collegato alla cantina"

    if not label_ids:
        return None

    cur.execute(
        """
        UPDATE label_collaborators
        SET active=FALSE, updated_at=now()
        WHERE wine_label_id = ANY(%s)
          AND active=TRUE
          AND collaborator_user_id<>%s
        """,
        (label_ids, int(studio_user_id)),
    )

    for label_id in label_ids:
        cur.execute(
            """
            INSERT INTO label_collaborators
              (wine_label_id, collaborator_user_id, role,
               can_view, can_edit, can_media, can_export, can_publish,
               commission_rate, active, created_at, updated_at)
            VALUES
              (%s,%s,'studio',TRUE,%s,%s,FALSE,FALSE,0,TRUE,now(),now())
            ON CONFLICT (wine_label_id, collaborator_user_id)
            WHERE active=TRUE
            DO UPDATE SET
              role='studio',
              can_view=TRUE,
              can_edit=EXCLUDED.can_edit,
              can_media=EXCLUDED.can_media,
              can_export=FALSE,
              can_publish=FALSE,
              commission_rate=0,
              active=TRUE,
              updated_at=now()
            """,
            (
                int(label_id),
                int(studio_user_id),
                bool(sc.get("can_edit")),
                bool(sc.get("can_edit") or sc.get("can_create")),
            ),
        )
    return None


@router.post("/app/wine/{wine_id}/management/set")
def wine_management_set(
    request: Request,
    wine_id: int,
    management_value: str = Form(...),
    return_to: str = Form(""),
):
    user = require_any_role(request, ("winery", "admin"))
    role = (user.get("role") or "").lower().strip()
    value = (management_value or "").strip().lower()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            wine = _load_wine(cur, int(wine_id))

            if role == "admin":
                active_wid = _admin_active_winery_id(cur, int(user["id"]))
                if not active_wid or int(active_wid) != int(wine["winery_id"]):
                    raise HTTPException(403, "Contesto cantina non corrisponde al vino")
            elif int(user["id"]) != int(wine["owner_user_id"]):
                raise HTTPException(403, "Forbidden")

            redirect_to = _safe_return_to(return_to, int(wine_id))

            if value == "invite":
                return RedirectResponse(
                    f"/app/winery/settings?source_wine_id={int(wine_id)}#invite-studio",
                    status_code=303,
                )

            label_ids = _wine_label_ids(cur, int(wine_id))

            if value == "self":
                if label_ids:
                    cur.execute(
                        """
                        UPDATE label_collaborators
                        SET active=FALSE, updated_at=now()
                        WHERE wine_label_id = ANY(%s)
                          AND active=TRUE
                        """,
                        (label_ids,),
                    )
                conn.commit()
                return RedirectResponse(
                    _with_notice(redirect_to, "msg", "Gestione interna attivata"),
                    status_code=303,
                )

            if value.startswith("studio:"):
                try:
                    studio_user_id = int(value.split(":", 1)[1])
                except Exception:
                    studio_user_id = 0

                if studio_user_id <= 0:
                    conn.rollback()
                    return RedirectResponse(
                        _with_notice(redirect_to, "err", "Studio non valido"),
                        status_code=303,
                    )

                err = _assign_wine_management(cur, wine, label_ids, studio_user_id)
                if err:
                    conn.rollback()
                    return RedirectResponse(
                        _with_notice(redirect_to, "err", err),
                        status_code=303,
                    )

                conn.commit()
                return RedirectResponse(
                    _with_notice(redirect_to, "msg", "Studio assegnato al lotto"),
                    status_code=303,
                )

            conn.rollback()
            return RedirectResponse(
                _with_notice(redirect_to, "err", "Scelta gestione non valida"),
                status_code=303,
            )


@router.get("/app/wine/{wine_id}", response_class=HTMLResponse)
def wine_hub(request: Request, wine_id: int, tab: str | None = None):
    """
    Overview vino.

    Compat:
      - /app/wine/{id}?tab=images|compliance|export -> redirect alle pagine dedicate.
    """
    user = require_any_role(request, ("winery", "studio", "admin"))

    uid = int(user["id"])
    role = (user.get("role") or "").lower().strip()

    tab = (tab or "").strip().lower()

    if tab == "images":
        return RedirectResponse(f"/app/wine/{int(wine_id)}/images", status_code=303)

    if tab == "compliance":
        return RedirectResponse(f"/app/wine/{int(wine_id)}/compliance", status_code=303)

    if tab == "export":
        return RedirectResponse(f"/app/wine/{int(wine_id)}/export", status_code=303)

    balances = {"wine": 0, "generic": 0}

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            balances = _balances(cur, uid)
            wine = _load_wine(cur, int(wine_id))

            if role == "admin":
                active_wid = _admin_active_winery_id(cur, uid)

                if not active_wid:
                    return RedirectResponse(
                        "/admin?err=Seleziona%20prima%20una%20cantina",
                        status_code=303,
                    )

                if int(active_wid) != int(wine["winery_id"]):
                    raise HTTPException(403, "Contesto cantina non corrisponde al vino")

            elif role == "winery":
                if int(uid) != int(wine["owner_user_id"]):
                    raise HTTPException(403, "Forbidden")

            elif role == "studio":
                if not _studio_can_access_wine(cur, uid, int(wine["winery_id"])):
                    raise HTTPException(403, "Forbidden")

            assets = _wine_assets(cur, int(wine_id))

            cur.execute(
                "SELECT COUNT(*)::int AS cnt FROM wine_labels WHERE wine_id=%s",
                (int(wine_id),),
            )
            labels_count = int((cur.fetchone() or {}).get("cnt") or 0)

            cur.execute(
                """
                SELECT COUNT(*)::int AS cnt
                FROM wine_labels
                WHERE wine_id=%s AND public_enabled=TRUE
                """,
                (int(wine_id),),
            )
            pub_count = int((cur.fetchone() or {}).get("cnt") or 0)

            labels = _labels_for_wine(cur, int(wine_id), role, uid)
            label_ids = [int(row["label_id"]) for row in labels]
            management = _label_management_map(cur, label_ids)
            connected_studios = _connected_studios(cur, int(wine["winery_id"])) if role in ("winery", "admin") else []

    app_base = getattr(request.app.state, "app_base_url", "").rstrip("/")

    winery_name = wine.get("winery_name") or "-"
    wine_name = wine.get("wine_name") or "-"
    vintage = (wine.get("vintage") or "").strip()
    lot = (wine.get("lot") or "").strip()
    updated_at = _fmt_ts(int(wine.get("updated_at") or 0))

    slug = (wine.get("slug") or "").strip()
    pub_url = _public_url(app_base, slug) if slug else ""

    is_published = pub_count > 0
    status_badge = pill("Pubblicato", "green") if is_published else pill("Bozza", "muted")

    actions = (
        pill(f"wine: {balances.get('wine', 0)}", "green") + " " +
        pill(f"generic: {balances.get('generic', 0)}") + " " +
        top_actions(
            ("/app/start", "Menu"),
            ("/app/dashboard", "Dashboard"),
            ("/app/labels/search", "Ricerca avanzata"),
            ("/logout", "Logout"),
        )
    )

    public_action = ""
    if is_published and pub_url:
        public_action = f"""
        <a class="btn" href="{esc(pub_url)}" target="_blank">
          Apri pubblica
        </a>
        """
    else:
        public_action = """
        <span class="pill pill-muted">
          Pubblica per attivare link
        </span>
        """

    publish_action = ""
    if role in ("winery", "admin"):
        if is_published:
            publish_action = f"""
            <form method="post" action="/app/wine/{int(wine_id)}/unpublish" style="display:inline">
              <button class="btn" type="submit">Rendi bozza</button>
            </form>
            """
        else:
            publish_action = f"""
            <form method="post" action="/app/wine/{int(wine_id)}/publish" style="display:inline">
              <button class="btn btn-primary" type="submit">Pubblica</button>
            </form>
            """

            if role == "admin":
                publish_action += f"""
                <form method="post" action="/app/wine/{int(wine_id)}/publish" style="display:inline"
                      onsubmit="return confirm('Forzare la pubblicazione anche se i dati obbligatori sono incompleti? Usare solo per test, demo o casi eccezionali.');">
                  <input type="hidden" name="force" value="1">
                  <button class="btn btn-danger-soft" type="submit">Forza pubblicazione</button>
                </form>
                """

            if role == "admin":
                publish_action += f"""
                <form method="post" action="/app/wine/{int(wine_id)}/publish" style="display:inline"
                      onsubmit="return confirm('Forzare la pubblicazione anche se i dati obbligatori sono incompleti? Usare solo per test o casi eccezionali.');">
                  <input type="hidden" name="force" value="1">
                  <button class="btn btn-danger-soft" type="submit">Forza pubblicazione</button>
                </form>
                """

    new_label_action = ""
    if role in ("winery", "admin"):
        new_label_action = f"""
        <a class="btn btn-primary" href="/app/new-label?wine_id={int(wine_id)}">
          + Etichetta
        </a>
        """

    front_card = _asset_card("front", assets.get("front"), int(wine_id))
    back_card = _asset_card("back", assets.get("back"), int(wine_id))

    if labels:
        labels_html = "".join(_label_row(r, role) for r in labels)
    else:
        empty_msg = (
            "Nessuna etichetta assegnata a questo studio."
            if role == "studio"
            else "Nessuna etichetta. Crea una etichetta front/back."
        )

        labels_html = f"""
        <div class="card wineHubEmptyLabels">
          <div class="wineHubEmptyIcon">🏷️</div>
          <div>
            <div class="h2">Nessuna etichetta</div>
            <div class="p">{esc(empty_msg)}</div>
            <div style="margin-top:16px">
              {new_label_action}
            </div>
          </div>
        </div>
        """

    vintage_html = f"<span>Annata <b>{esc(vintage)}</b></span>" if vintage else ""
    lot_html = f"<span>Lotto <b>{esc(lot)}</b></span>" if lot else ""
    slug_html = f"<span>Slug <b>{esc(slug or '-')}</b></span>"

    studio_note = ""
    if role == "studio":
        studio_note = """
        <div class="note" style="margin-top:18px">
          In questa schermata lo studio vede solo il lavoro rilevante per sé:
          soprattutto le etichette assegnate.
        </div>
        """

    management_section = _management_section(labels, management, role, int(wine_id), connected_studios)

    body = f"""
    <section class="wineHubWrap">
      <div class="wineHubHero">
        <div>
          <div class="wineHubEyebrow">Scheda lotto vino</div>

          <div class="wineHubTitleRow">
            <div class="h1">{esc(wine_name)}</div>
            {status_badge}
          </div>

          <div class="p">
            {esc(winery_name)} · aggiornato il {esc(updated_at)}
          </div>

          <div class="wineHubMeta">
            {vintage_html}
            {lot_html}
            {slug_html}
          </div>
        </div>

        <div class="wineHubStats">
          <div class="wineHubStat">
            <span>Etichette</span>
            <b>{labels_count}</b>
          </div>

          <div class="wineHubStat">
            <span>Pubbliche</span>
            <b>{pub_count}</b>
          </div>
        </div>
      </div>

      <div class="wineHubTabs">
        <a class="wineHubTab active" href="/app/wine/{int(wine_id)}">Overview</a>
        <a class="wineHubTab" href="/app/wine/{int(wine_id)}/images">Immagini</a>
        <a class="wineHubTab" href="/app/wine/{int(wine_id)}/compliance">Compliance</a>
        <a class="wineHubTab" href="/app/wine/{int(wine_id)}/export">Export</a>
      </div>

      <div class="card wineHubActionBar">
        <div>
          <div class="h2">Azioni lotto</div>
          <div class="p">
            Gestisci fronte/retro, immagini, compliance, pubblicazione ed esportazione QR.
          </div>
        </div>

        <div class="wineHubActionButtons">
          {new_label_action}
          {public_action}
          {publish_action}
        </div>
      </div>

      <div class="wineHubFlow">
        <a href="/app/wine/{int(wine_id)}/images">
          <span>1</span>
          <b>Immagini</b>
          <small>Carica fronte e retro</small>
        </a>

        <a href="/app/wine/{int(wine_id)}/compliance">
          <span>2</span>
          <b>Compliance</b>
          <small>Compila dati obbligatori</small>
        </a>

        <a href="/app/wine/{int(wine_id)}/export">
          <span>3</span>
          <b>Export</b>
          <small>Scarica QR per stampa</small>
        </a>
      </div>

      <div class="wineHubAssetGrid">
        {front_card}
        {back_card}
      </div>

      {studio_note}

      {management_section}

      <div class="card wineHubLabelsCard">
        <div class="wineHubCardHead">
          <div>
            <div class="wineHubSmallLabel">Etichette collegate</div>
            <div class="h2">Etichette del vino</div>
            {'' if role == 'studio' else '<div class="p" style="margin-top:4px">Assegna ogni etichetta allo studio grafico che la seguirà operativamente.</div>'}
          </div>
          {new_label_action}
        </div>

        <div class="wineHubLabelsList">
          {labels_html}
        </div>
      </div>

      <div class="note" style="margin-top:18px">
        Flusso consigliato: <b>Immagini → Compliance → Export</b>.
        La pubblicazione la fa sempre la cantina o l’admin.
      </div>

      <style>
        .wineHubWrap {{
          max-width:1180px;
          margin:0 auto;
        }}

        .wineHubHero {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:28px;
          overflow:hidden;
          box-shadow:0 24px 80px rgba(2,8,23,.08);
          background:
            radial-gradient(circle at 8% 12%, rgba(191,245,230,.58), transparent 34%),
            radial-gradient(circle at 92% 8%, rgba(207,232,255,.58), transparent 34%),
            linear-gradient(135deg,rgba(255,255,255,.96),rgba(248,252,250,.92));
          padding:30px;
          display:grid;
          grid-template-columns:minmax(0,1.35fr) 260px;
          gap:24px;
          align-items:end;
        }}

        .wineHubEyebrow {{
          display:inline-flex;
          padding:7px 12px;
          border-radius:999px;
          background:rgba(20,184,166,.10);
          color:#0f766e;
          font-size:12px;
          font-weight:950;
          letter-spacing:.08em;
          text-transform:uppercase;
        }}

        .wineHubTitleRow {{
          display:flex;
          gap:12px;
          align-items:center;
          flex-wrap:wrap;
        }}

        .wineHubMeta {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:16px;
        }}

        .wineHubMeta span {{
          display:inline-flex;
          padding:8px 11px;
          border-radius:999px;
          background:rgba(255,255,255,.72);
          border:1px solid rgba(2,8,23,.07);
          color:#475569;
          font-size:12px;
          font-weight:850;
        }}

        .wineHubMeta b {{
          color:#0f172a;
          margin-left:4px;
        }}

        .wineHubStats {{
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:12px;
        }}

        .wineHubStat {{
          border:1px solid rgba(2,8,23,.07);
          background:rgba(255,255,255,.72);
          border-radius:22px;
          padding:16px;
        }}

        .wineHubStat span {{
          display:block;
          font-size:12px;
          color:#64748b;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.07em;
        }}

        .wineHubStat b {{
          display:block;
          margin-top:8px;
          font-size:34px;
          line-height:1;
          font-weight:950;
        }}

        .wineHubTabs {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:18px;
        }}

        .wineHubTab {{
          display:inline-flex;
          align-items:center;
          justify-content:center;
          padding:12px 16px;
          border-radius:18px;
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.76);
          font-weight:950;
          box-shadow:0 12px 30px rgba(2,8,23,.04);
        }}

        .wineHubTab.active {{
          background:linear-gradient(135deg,rgba(191,245,230,.95),rgba(207,232,255,.88));
          border-color:rgba(20,184,166,.18);
        }}

        .wineHubActionBar {{
          margin-top:18px;
          display:flex;
          justify-content:space-between;
          gap:18px;
          align-items:center;
        }}

        .wineHubActionButtons {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          justify-content:flex-end;
          align-items:center;
        }}

        .wineHubFlow {{
          display:grid;
          grid-template-columns:repeat(3,minmax(0,1fr));
          gap:14px;
          margin-top:18px;
        }}

        .wineHubFlow a {{
          display:flex;
          gap:12px;
          align-items:flex-start;
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          padding:16px;
          background:rgba(255,255,255,.78);
          box-shadow:0 12px 30px rgba(2,8,23,.04);
        }}

        .wineHubFlow a:hover {{
          transform:translateY(-2px);
          box-shadow:0 20px 50px rgba(2,8,23,.08);
        }}

        .wineHubFlow span {{
          width:34px;
          height:34px;
          border-radius:13px;
          display:flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.92),rgba(207,232,255,.92));
          font-weight:950;
          flex:0 0 auto;
        }}

        .wineHubFlow b {{
          display:block;
          font-size:15px;
          font-weight:950;
        }}

        .wineHubFlow small {{
          display:block;
          margin-top:3px;
          color:#64748b;
          font-size:12px;
          font-weight:750;
          line-height:1.35;
        }}

        .wineHubAssetGrid {{
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:18px;
          margin-top:18px;
        }}

        .wineHubAssetCard {{
          padding:22px;
        }}

        .wineHubManagementCard {{
          margin-top:18px;
          padding:22px;
        }}

        .wineHubManagementList {{
          display:grid;
          gap:10px;
        }}

        .wineHubManagementRow {{
          display:grid;
          grid-template-columns:minmax(0,1fr) minmax(180px,.8fr) auto;
          gap:12px;
          align-items:center;
          padding:12px 13px;
          border-radius:16px;
          background:rgba(248,250,252,.78);
        }}

        .wineHubManagementRow b,
        .wineHubManagementRow span {{
          display:block;
        }}

        .wineHubManagementRow b {{
          font-weight:950;
        }}

        .wineHubManagementRow span {{
          margin-top:3px;
          color:#64748b;
          font-weight:750;
        }}

        .wineHubManagementRow em {{
          display:inline-flex;
          padding:5px 9px;
          border-radius:999px;
          background:white;
          color:#475569;
          font-style:normal;
          font-weight:950;
        }}

        .wineHubManagementRow-assigned em {{
          background:rgba(236,253,245,.88);
          color:#0f766e;
        }}

        .wineHubManagementRow-pending em {{
          background:rgba(255,251,235,.92);
          color:#92400e;
        }}

        .wineHubManagementPicker {{
          display:grid;
          grid-template-columns:auto minmax(160px, 1fr) auto;
          gap:8px;
          align-items:center;
        }}

        .wineHubManagementPicker label {{
          margin:0;
          font-size:12px;
          font-weight:900;
          color:#475569;
        }}

        .wineHubManagementPicker select {{
          min-width:0;
        }}

        .wineHubManagementEmpty {{
          padding:14px;
          border-radius:16px;
          background:rgba(248,250,252,.78);
          color:#64748b;
          font-weight:800;
        }}

        .wineHubCardHead {{
          display:flex;
          justify-content:space-between;
          gap:14px;
          align-items:flex-start;
          margin-bottom:16px;
        }}

        .wineHubSmallLabel {{
          color:#64748b;
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.08em;
        }}

        .wineHubImageBox {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          overflow:hidden;
          background:#fff;
        }}

        .wineHubImageBox img {{
          width:100%;
          height:320px;
          object-fit:cover;
          display:block;
        }}

        .wineHubImagePlaceholder {{
          min-height:260px;
          border:1px dashed rgba(2,8,23,.16);
          border-radius:22px;
          background:
            radial-gradient(circle at 20% 10%, rgba(191,245,230,.45), transparent 50%),
            rgba(255,255,255,.70);
          display:flex;
          align-items:center;
          justify-content:center;
          flex-direction:column;
          text-align:center;
          padding:24px;
        }}

        .wineHubImageIcon {{
          width:58px;
          height:58px;
          border-radius:20px;
          display:flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.85),rgba(207,232,255,.85));
          font-size:26px;
          margin-bottom:12px;
        }}

        .wineHubImagePlaceholder b {{
          font-size:17px;
          font-weight:950;
        }}

        .wineHubImagePlaceholder span {{
          color:#64748b;
          font-size:13px;
          font-weight:750;
          margin-top:4px;
        }}

        .wineHubLabelsCard {{
          margin-top:18px;
          padding:22px;
        }}

        .wineHubLabelsList {{
          display:grid;
          gap:12px;
        }}

        .wineHubLabelRow {{
          display:flex;
          justify-content:space-between;
          gap:14px;
          align-items:center;
          padding:15px;
          border-radius:20px;
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.76);
        }}

        .wineHubLabelRow:hover {{
          box-shadow:0 18px 45px rgba(2,8,23,.07);
          border-color:rgba(20,184,166,.18);
        }}

        .wineHubLabelTitle {{
          display:flex;
          gap:10px;
          align-items:center;
          flex-wrap:wrap;
          font-weight:950;
          letter-spacing:-.2px;
        }}

        .wineHubLabelMeta {{
          margin-top:6px;
          color:#64748b;
          font-size:13px;
          font-weight:750;
          line-height:1.4;
        }}

        .wineHubLabelActions {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          align-items:center;
          justify-content:flex-end;
        }}

        .wineHubEmptyLabels {{
          display:flex;
          gap:16px;
          align-items:flex-start;
          box-shadow:none;
          background:rgba(255,255,255,.72);
        }}

        .wineHubEmptyIcon {{
          width:58px;
          height:58px;
          border-radius:20px;
          display:flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.85),rgba(207,232,255,.85));
          font-size:26px;
          flex:0 0 auto;
        }}

        @media(max-width:980px) {{
          .wineHubHero,
          .wineHubAssetGrid {{
            grid-template-columns:1fr;
          }}

          .wineHubManagementRow {{
            grid-template-columns:1fr;
            align-items:flex-start;
          }}

          .wineHubManagementPicker {{
            grid-template-columns:1fr;
          }}

          .wineHubFlow {{
            grid-template-columns:1fr;
          }}

          .wineHubActionBar {{
            flex-direction:column;
            align-items:flex-start;
          }}

          .wineHubActionButtons {{
            justify-content:flex-start;
          }}

          .wineHubStats {{
            max-width:360px;
          }}
        }}

        @media(max-width:640px) {{
          .wineHubHero {{
            padding:22px;
          }}

          .wineHubStats {{
            grid-template-columns:1fr;
          }}

          .wineHubActionButtons .btn,
          .wineHubActionButtons form,
          .wineHubActionButtons button,
          .wineHubCardHead .btn,
          .wineHubLabelActions .btn {{
            width:100%;
          }}

          .wineHubCardHead,
          .wineHubLabelRow {{
            flex-direction:column;
            align-items:flex-start;
          }}

          .wineHubLabelActions {{
            width:100%;
            justify-content:flex-start;
          }}
        }}
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Lotto vino",
        subtitle="Overview lotto",
        body_html=body,
        actions_html=actions,
        user_email=user.get("email", ""),
        role=role,
        credits=balances,
    ))
