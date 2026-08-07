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
          wl.public_enabled,
          qw.wine_name,
          qw.vintage,
          qw.lot AS wine_lot,
          w.name AS winery_name,
          w.owner_user_id
        FROM wine_labels wl
        JOIN qr_wines qw ON qw.id = wl.wine_id
        JOIN wineries w ON w.id = wl.winery_id
        WHERE wl.id=%s
        LIMIT 1
        """,
        (int(label_id),),
    )
    r = cur.fetchone()
    if not r:
        raise HTTPException(404, "Etichetta non trovata")
    return r


def _is_winery_owner(user: dict, label: dict) -> bool:
    return (user.get("role") or "").lower().strip() == "winery" and int(user["id"]) == int(label["owner_user_id"])


def _is_admin(user: dict) -> bool:
    return (user.get("role") or "").lower().strip() == "admin"


def _load_connected_studios(cur, winery_id: int) -> list[dict]:
    """
    Studi collegati alla cantina (studio_clients).
    """
    cur.execute(
        """
        SELECT
          u.id AS studio_user_id,
          u.email,
          s.company_name,
          sc.can_view,
          sc.can_edit,
          sc.can_create
        FROM studio_clients sc
        JOIN users u ON u.id = sc.studio_user_id
        JOIN studios s ON s.user_id = u.id
        WHERE sc.winery_id=%s AND sc.can_view=TRUE
          AND lower(u.role)='studio'
        ORDER BY lower(s.company_name), lower(u.email)
        """,
        (int(winery_id),),
    )
    return cur.fetchall() or []


def _load_current_collabs(cur, label_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT
          lc.id,
          lc.wine_label_id,
          lc.collaborator_user_id,
          lc.role,
          lc.can_view,
          lc.can_edit,
          lc.can_media,
          lc.can_publish,
          lc.can_export,
          lc.active,
          lc.created_at,
          lc.updated_at,
          u.email,
          COALESCE(s.company_name,'') AS company_name
        FROM label_collaborators lc
        JOIN users u ON u.id = lc.collaborator_user_id
        LEFT JOIN studios s ON s.user_id = u.id
        WHERE lc.wine_label_id=%s
        ORDER BY lc.active DESC, lc.id DESC
        """,
        (int(label_id),),
    )
    return cur.fetchall() or []


def _safe_return_to(return_to: str, label: dict) -> str:
    return_to = (return_to or "").strip()
    if return_to.startswith("/app/") and not return_to.startswith("//"):
        return return_to
    if label.get("wine_id"):
        return f"/app/wine/{int(label['wine_id'])}#gestione-grafica"
    return f"/app/label/{int(label['label_id'])}/acl"


def _with_notice(url: str, key: str, message: str) -> str:
    base, fragment = (url or "").split("#", 1) if "#" in (url or "") else (url, "")
    sep = "&" if "?" in base else "?"
    out = f"{base}{sep}{key}={quote_plus(message)}"
    if fragment:
        out = f"{out}#{fragment}"
    return out


def _assign_label_management(cur, label: dict, studio_user_id: int) -> str | None:
    cur.execute(
        """
        SELECT can_view, can_edit, can_create
        FROM studio_clients
        WHERE winery_id=%s
          AND studio_user_id=%s
          AND can_view=TRUE
        LIMIT 1
        """,
        (int(label["winery_id"]), int(studio_user_id)),
    )
    sc = cur.fetchone()
    if not sc:
        return "Studio non collegato alla cantina"

    cur.execute(
        """
        UPDATE label_collaborators
        SET active=FALSE, updated_at=now()
        WHERE wine_label_id=%s
          AND active=TRUE
          AND collaborator_user_id<>%s
        """,
        (int(label["label_id"]), int(studio_user_id)),
    )

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
            int(label["label_id"]),
            int(studio_user_id),
            bool(sc.get("can_edit")),
            bool(sc.get("can_edit") or sc.get("can_create")),
        ),
    )
    return None


@router.get("/app/label/{label_id}/acl", response_class=HTMLResponse)
def label_acl(request: Request, label_id: int, msg: str = "", err: str = ""):
    u = require_any_role(request, ("winery", "studio", "admin"))
    role = (u.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label(cur, int(label_id))

            # access control:
            # - admin sempre
            # - winery owner sempre
            # - studio solo se ha can_view su cantina (studio_clients) (qui facciamo controllo semplice)
            if not (_is_admin(u) or _is_winery_owner(u, label) or role == "studio"):
                raise HTTPException(403, "Forbidden")

            # se studio: deve avere relazione con cantina
            if role == "studio":
                cur.execute(
                    """
                    SELECT 1
                    FROM studio_clients
                    WHERE studio_user_id=%s AND winery_id=%s AND can_view=TRUE
                    LIMIT 1
                    """,
                    (int(u["id"]), int(label["winery_id"])),
                )
                if not cur.fetchone():
                    raise HTTPException(403, "Forbidden")

            connected = []
            if _is_admin(u) or _is_winery_owner(u, label):
                connected = _load_connected_studios(cur, int(label["winery_id"]))

            collabs = _load_current_collabs(cur, int(label_id))

    # UI header
    actions = top_actions(
        (f"/app/label/{int(label_id)}", "← Etichetta"),
        ("/app/dashboard", "Dashboard"),
        ("/logout", "Logout"),
    )

    badge = pill("Pubblica", "green") if bool(label.get("public_enabled")) else pill("Bozza", "warn")

    # current assigned
    if collabs:
        rows = []
        for c in collabs:
            status = pill("attivo", "green") if bool(c.get("active")) else pill("inattivo", "muted")
            who = (c.get("company_name") or "").strip()
            if who:
                who = f"{who} · {c.get('email') or ''}"
            else:
                who = c.get("email") or "-"
            rows.append(f"""
              <tr>
                <td style="white-space:nowrap">{status}</td>
                <td><b>{esc(who)}</b><div class="muted" style="font-size:12px;margin-top:4px">
                    ruolo: {esc(c.get('role') or '')}
                </div></td>
                <td class="muted" style="font-size:12px">
                  view={str(bool(c.get('can_view'))).lower()} · edit={str(bool(c.get('can_edit'))).lower()} ·
                  media={str(bool(c.get('can_media'))).lower()} · export={str(bool(c.get('can_export'))).lower()} ·
                  publish={str(bool(c.get('can_publish'))).lower()}
                </td>
                <td style="white-space:nowrap" class="muted">{esc(_fmt_ts(None))}</td>
              </tr>
            """)
        current_html = f"""
        <div class="card" style="margin-top:14px">
          <div class="h2">Collaboratori assegnati</div>
          <div class="p">Chi può lavorare su questa etichetta.</div>
          <div style="margin-top:12px;overflow:auto">
            <table>
              <thead>
                <tr>
                  <th>Stato</th>
                  <th>Collaboratore</th>
                  <th>Permessi</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {''.join(rows)}
              </tbody>
            </table>
          </div>
        </div>
        """
    else:
        current_html = """
        <div class="card" style="margin-top:14px">
          <div class="h2">Collaboratori assegnati</div>
          <div class="p">Nessun collaboratore assegnato a questa etichetta.</div>
        </div>
        """

    # assignment form (only winery/admin)
    assign_html = ""
    if _is_admin(u) or _is_winery_owner(u, label):
        self_html = f"""
        <div class="card" style="margin-top:14px">
          <div class="h2">Chi lavora su questa etichetta?</div>
          <div class="p">
            Scegli il responsabile operativo di questa singola etichetta. Il collegamento generale
            con gli studi resta gestito da <b>studio_clients</b>; qui decidi chi lavora su questo QR.
          </div>
          <form method="post" action="/app/label/{int(label_id)}/acl/clear" style="margin-top:12px">
            <button class="btn" type="submit">Gestisco io</button>
          </form>
        </div>
        """
        if connected:
            opts = ["<option value=''>— Seleziona studio —</option>"]
            for s in connected:
                label_txt = f"{(s.get('company_name') or '').strip()} · {(s.get('email') or '').strip()}"
                opts.append(f"<option value='{int(s['studio_user_id'])}'>{esc(label_txt)}</option>")

            assign_html = f"""
            {self_html}
            <div class="card" style="margin-top:14px;max-width:980px">
              <div class="h2">Assegna a Studio già collegato</div>
              <div class="p">
                Scegli quale studio grafico seguirà questa specifica etichetta della cantina
                <b>{esc(label.get('winery_name') or '')}</b>. Puoi usare studi diversi per etichette diverse:
                la pubblicazione resta sempre alla cantina o all’admin.
              </div>

              <form method="post" action="/app/label/{int(label_id)}/acl/assign" style="margin-top:12px">
                <label>Studio</label>
                <select name="studio_user_id" required>
                  {''.join(opts)}
                </select>

                <div style="margin-top:12px">
                  <label>Permessi consigliati</label>
                  <div class="note" style="margin-top:0">
                    Vista, modifica, media ed export attivi. Pubblicazione disattivata: il controllo resta alla cantina.
                  </div>
                </div>

                <div class="grid2" style="margin-top:10px">
                  <div>
                    <label><input type="checkbox" name="can_view" checked> view</label>
                    <label><input type="checkbox" name="can_edit" checked> edit</label>
                    <label><input type="checkbox" name="can_media" checked> media</label>
                  </div>
                  <div>
                    <label><input type="checkbox" name="can_export" checked> export</label>
                    <span class="note">Pubblicazione non assegnabile agli studi.</span>
                  </div>
                </div>

                <div class="row" style="margin-top:14px">
                  <button class="btn btn-primary" type="submit">Assegna a questo studio</button>
                  <a class="btn" href="/app/label/{int(label_id)}">Torna etichetta</a>
                </div>
              </form>

              <div class="note" style="margin-top:14px">
                Se non vedi lo studio in lista, prima collegalo alla cantina tramite invito/registrazione.
              </div>
            </div>
            """
        else:
            assign_html = f"""
            {self_html}
            <div class="card" style="margin-top:14px">
              <div class="h2">Invita nuovo Studio Grafico</div>
              <div class="p">
                Nessuno studio risulta collegato alla cantina <b>{esc(label.get('winery_name') or '')}</b>.
                Collega prima uno studio grafico, poi torna qui per assegnarlo a questa etichetta.
              </div>
              <div style="margin-top:12px">
                <a class="btn btn-primary" href="/app/winery/settings">Gestisci studi grafici autorizzati</a>
              </div>
            </div>
            """

    body = f"""
    <div class="h1" style="margin-top:14px">Studio grafico assegnato {badge}</div>
    <div class="p">{esc(label.get('winery_name') or '')} · {esc(label.get('wine_name') or '')}</div>

    {current_html}
    {assign_html}

    <div class="note" style="margin-top:16px">
      Regola consigliata: la cantina assegna ogni etichetta allo studio grafico corretto.
      Lo studio lavora, la cantina mantiene il controllo e pubblica.
    </div>
    """

    return HTMLResponse(page(
        title="QRFACILE · Accessi etichetta",
        subtitle="Accessi",
        body_html=body,
        actions_html=actions,
        msg=msg,
        err=err,
        user_email=u.get("email",""),
        role=role,
        credits=None,
    ))


@router.post("/app/label/{label_id}/acl/assign")
def label_acl_assign(
    request: Request,
    label_id: int,
    studio_user_id: int = Form(...),
    commission_rate: str = Form("0.15"),
    can_view: str = Form(None),
    can_edit: str = Form(None),
    can_media: str = Form(None),
    can_export: str = Form(None),
    can_publish: str = Form(None),
):
    u = require_any_role(request, ("winery", "admin"))

    # parse bools
    bv = bool(can_view)
    be = bool(can_edit)
    bm = bool(can_media)
    bx = bool(can_export)
    bp = bool(can_publish)

    try:
        cr = float(str(commission_rate or "0.15").strip())
        if cr < 0:
            cr = 0.0
        if cr > 0.5:
            cr = 0.5
    except Exception:
        cr = 0.15

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label(cur, int(label_id))

            # must be winery owner or admin
            if not (_is_admin(u) or _is_winery_owner(u, label)):
                raise HTTPException(403, "Forbidden")

            # ensure studio is connected to this winery
            cur.execute(
                """
                SELECT 1
                FROM studio_clients
                WHERE winery_id=%s AND studio_user_id=%s AND can_view=TRUE
                LIMIT 1
                """,
                (int(label["winery_id"]), int(studio_user_id)),
            )
            if not cur.fetchone():
                conn.rollback()
                return RedirectResponse(f"/app/label/{int(label_id)}/acl?err=Studio%20non%20collegato%20alla%20cantina", status_code=303)

            # upsert active collaborator
            cur.execute(
                """
                INSERT INTO label_collaborators
                  (wine_label_id, collaborator_user_id, role,
                   can_view, can_edit, can_media, can_export, can_publish,
                   commission_rate, active, created_at, updated_at)
                VALUES
                  (%s,%s,'studio',%s,%s,%s,%s,%s,%s,TRUE,now(),now())
                ON CONFLICT (wine_label_id, collaborator_user_id)
                WHERE active=TRUE
                DO UPDATE SET
                  role='studio',
                  can_view=EXCLUDED.can_view,
                  can_edit=EXCLUDED.can_edit,
                  can_media=EXCLUDED.can_media,
                  can_export=EXCLUDED.can_export,
                  can_publish=EXCLUDED.can_publish,
                  commission_rate=EXCLUDED.commission_rate,
                  updated_at=now()
                """,
                (int(label_id), int(studio_user_id), bv, be, bm, bx, bp, cr),
            )

            conn.commit()

    return RedirectResponse(f"/app/label/{int(label_id)}/acl?msg=Studio%20assegnato", status_code=303)


@router.post("/app/label/{label_id}/acl/clear")
def label_acl_clear(request: Request, label_id: int):
    u = require_any_role(request, ("winery", "admin"))

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label(cur, int(label_id))

            if not (_is_admin(u) or _is_winery_owner(u, label)):
                raise HTTPException(403, "Forbidden")

            cur.execute(
                """
                UPDATE label_collaborators
                SET active=FALSE, updated_at=now()
                WHERE wine_label_id=%s AND active=TRUE
                """,
                (int(label_id),),
            )
            conn.commit()

    return RedirectResponse(f"/app/label/{int(label_id)}/acl?msg=Gestione%20interna%20attivata", status_code=303)


@router.post("/app/label/{label_id}/management/set")
def label_management_set(
    request: Request,
    label_id: int,
    management_value: str = Form(...),
    return_to: str = Form(""),
):
    u = require_any_role(request, ("winery", "admin"))
    value = (management_value or "").strip().lower()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label(cur, int(label_id))

            if not (_is_admin(u) or _is_winery_owner(u, label)):
                raise HTTPException(403, "Forbidden")

            redirect_to = _safe_return_to(return_to, label)

            if value == "invite":
                return RedirectResponse(
                    f"/app/winery/settings?source_label_id={int(label_id)}#invite-studio",
                    status_code=303,
                )

            if value == "self":
                cur.execute(
                    """
                    UPDATE label_collaborators
                    SET active=FALSE, updated_at=now()
                    WHERE wine_label_id=%s AND active=TRUE
                    """,
                    (int(label_id),),
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

                err = _assign_label_management(cur, label, studio_user_id)
                if err:
                    conn.rollback()
                    return RedirectResponse(
                        _with_notice(redirect_to, "err", err),
                        status_code=303,
                    )

                conn.commit()
                return RedirectResponse(
                    _with_notice(redirect_to, "msg", "Studio assegnato"),
                    status_code=303,
                )

            conn.rollback()
            return RedirectResponse(
                _with_notice(redirect_to, "err", "Scelta gestione non valida"),
                status_code=303,
            )
