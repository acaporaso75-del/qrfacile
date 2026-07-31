import time
import secrets
from typing import Set

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.util import new_slug
from qrfacile_app.auth_core import (
    require_any_role,
    studio_allowed_wineries,
    winery_id_for_owner,
)
from qrfacile_app.ui_shell import page, top_actions, pill, esc

router = APIRouter()

QR_WINES_QR_ITEM_UNIQUE_CONSTRAINT = "uq_qr_wines_qr_item_id"


def now() -> int:
    return int(time.time())


def _allowed_winery_ids(user: dict, need: str = "view") -> list[int]:
    role = (user.get("role") or "").lower().strip()

    if role == "admin":
        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id FROM wineries ORDER BY id")
                return [int(r["id"]) for r in (cur.fetchall() or [])]

    if role == "studio":
        return studio_allowed_wineries(int(user["id"]), need=need)

    wid = winery_id_for_owner(int(user["id"]))
    return [wid] if wid else []


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


def _columns(cur, table: str) -> Set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    return {r["column_name"] for r in (cur.fetchall() or [])}


def _wine(cur, wine_id: int) -> dict:
    cur.execute(
        """
        SELECT qw.id AS wine_id,
               qw.winery_id,
               qw.qr_item_id,
               qw.wine_name,
               qw.vintage,
               qw.lot,
               w.name AS winery_name
        FROM qr_wines qw
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


def _winery(cur, winery_id: int) -> dict:
    cur.execute(
        """
        SELECT id AS winery_id, name, owner_user_id
        FROM wineries
        WHERE id=%s
        LIMIT 1
        """,
        (int(winery_id),),
    )
    w = cur.fetchone()

    if not w:
        raise HTTPException(404, "Cantina non trovata")

    return w


def _connected_studios(cur, winery_id: int) -> list[dict]:
    """
    Studi collegati operativamente alla cantina.
    Non c'entra nulla con sconti/bonus commerciali.
    """
    cur.execute(
        """
        SELECT
          sc.studio_user_id,
          sc.can_view,
          sc.can_edit,
          sc.can_create,
          u.email,
          COALESCE(s.company_name, '') AS company_name
        FROM studio_clients sc
        JOIN users u ON u.id = sc.studio_user_id
        LEFT JOIN studios s ON s.user_id = u.id
        WHERE sc.winery_id=%s
          AND lower(u.role)='studio'
          AND sc.can_view=TRUE
        ORDER BY sc.created_at ASC, sc.studio_user_id ASC
        """,
        (int(winery_id),),
    )
    return cur.fetchall() or []


def _studio_assignment_box(
    *,
    section_no: int,
    studios: list[dict],
    invite_enabled: bool,
    context: str,
) -> str:
    opts = ["<option value='0'>Seleziona studio collegato</option>"]
    for st in studios:
        sid = int(st["studio_user_id"])
        name = ((st.get("company_name") or "").strip() or (st.get("email") or "Studio"))
        opts.append(f"<option value='{sid}'>{esc(name)}</option>")

    connected_disabled = "" if studios else "disabled"
    invite_html = ""
    if invite_enabled:
        invite_html = """
          <label class="newWineWorkOption">
            <input type="radio" name="studio_work_mode" value="invite">
            <span>
              <b>Invita nuovo Studio Grafico</b>
              <small>Creo un invito collegato a questo lavoro. Dopo l'accettazione lo studio arriva qui se lo schema supporta il contesto.</small>
            </span>
          </label>
          <div class="newWineWorkNested">
            <label>Email Studio Grafico</label>
            <input class="input" name="invite_studio_email" type="email" placeholder="studio@example.com">
          </div>
        """

    return f"""
    <div class="newWineSectionTitle" style="margin-top:24px">
      <span>{int(section_no)}</span>
      <div>
        <b>Chi lavora su questa etichetta?</b>
        <small>{esc(context)}</small>
      </div>
    </div>

    <div class="newWineWorkBox">
      <label class="newWineWorkOption">
        <input type="radio" name="studio_work_mode" value="self" checked>
        <span>
          <b>Gestisco io</b>
          <small>Nessuno studio viene assegnato ora.</small>
        </span>
      </label>

      <label class="newWineWorkOption">
        <input type="radio" name="studio_work_mode" value="connected" {connected_disabled}>
        <span>
          <b>Assegna a Studio già collegato</b>
          <small>Lo studio deve essere collegato alla cantina e poi assegnato a questa etichetta.</small>
        </span>
      </label>
      <div class="newWineWorkNested">
        <label>Studio collegato</label>
        <select name="assigned_studio_user_id" {connected_disabled}>
          {''.join(opts)}
        </select>
        <div class="note" style="margin-top:10px">
          Il collegamento generale resta in <b>studio_clients</b>; l'assegnazione operativa usa <b>label_collaborators</b>.
        </div>
      </div>

      {invite_html}
    </div>
    """


def _create_studio_invite_for_context(
    cur,
    *,
    winery_id: int,
    inviter_user_id: int,
    studio_email: str,
    wine_id: int | None = None,
    label_id: int | None = None,
) -> bool:
    studio_email = "".join((studio_email or "").split()).strip().lower()
    if not studio_email or "@" not in studio_email or "." not in studio_email:
        return False

    token = secrets.token_urlsafe(24)
    ts = now()
    exp = ts + 14 * 86400

    cols = [
        "token",
        "winery_id",
        "inviter_user_id",
        "studio_email",
        "can_view",
        "can_edit",
        "can_create",
        "created_at",
        "expires_at",
    ]
    vals = [token, int(winery_id), int(inviter_user_id), studio_email, True, True, False, ts, exp]

    invite_cols = _columns(cur, "studio_invites")
    if wine_id and "source_wine_id" in invite_cols:
        cols.append("source_wine_id")
        vals.append(int(wine_id))
    if label_id and "source_label_id" in invite_cols:
        cols.append("source_label_id")
        vals.append(int(label_id))

    placeholders = ",".join(["%s"] * len(vals))
    cur.execute(
        f"INSERT INTO studio_invites ({','.join(cols)}) VALUES ({placeholders})",
        tuple(vals),
    )
    return True


def _auto_assign_single_connected_studio(cur, label_id: int, winery_id: int) -> bool:
    """
    Se la cantina ha un solo studio collegato, lo assegna automaticamente
    alla nuova etichetta con permessi operativi standard.

    Ritorna True se ha assegnato, False altrimenti.
    """
    studios = _connected_studios(cur, int(winery_id))

    if len(studios) != 1:
        return False

    studio_user_id = int(studios[0]["studio_user_id"])

    cur.execute(
        """
        INSERT INTO label_collaborators
          (wine_label_id, collaborator_user_id, role,
           can_view, can_edit, can_media, can_export, can_publish,
           commission_rate, active, created_at, updated_at)
        VALUES
          (%s,%s,'studio',TRUE,TRUE,TRUE,TRUE,FALSE,0.0,TRUE,now(),now())
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
        (int(label_id), studio_user_id),
    )
    return True



def _assign_connected_studio_to_label(cur, label_id: int, winery_id: int, studio_user_id: int) -> bool:
    """
    Assegna uno studio collegato a una etichetta specifica.

    Regola:
    - lo studio resta studio;
    - la cantina resta proprietaria;
    - lo studio può lavorare operativamente;
    - la pubblicazione resta sempre cantina/admin.
    """
    cur.execute(
        """
        SELECT sc.studio_user_id, sc.can_view, sc.can_edit, sc.can_create
        FROM studio_clients sc
        JOIN users u ON u.id = sc.studio_user_id
        WHERE sc.winery_id=%s
          AND sc.studio_user_id=%s
          AND lower(u.role)='studio'
        LIMIT 1
        """,
        (int(winery_id), int(studio_user_id)),
    )
    sc = cur.fetchone()

    if not sc or not bool(sc.get("can_view")):
        return False

    can_view = True
    can_edit = bool(sc.get("can_edit"))
    can_media = bool(sc.get("can_edit"))
    can_export = bool(sc.get("can_edit") or sc.get("can_create"))
    can_publish = False

    cur.execute(
        """
        INSERT INTO label_collaborators
          (wine_label_id, collaborator_user_id, role,
           can_view, can_edit, can_media, can_export, can_publish,
           commission_rate, active, created_at, updated_at)
        VALUES
          (%s,%s,'studio',%s,%s,%s,%s,%s,0.0,TRUE,now(),now())
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
        (
            int(label_id),
            int(studio_user_id),
            can_view,
            can_edit,
            can_media,
            can_export,
            can_publish,
        ),
    )
    return True


# ============================================================
# NEW LOT - Nuovo lotto vino
# ============================================================

@router.get("/app/new-wine", response_class=HTMLResponse)
def new_wine_get(
    request: Request,
    winery_id: int = 0,
    wine_master_id: int = 0,
    msg: str = "",
    err: str = "",
):
    user = require_any_role(request, ("winery", "studio", "admin"))

    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    allowed_view = _allowed_winery_ids(user, need="view")

    if role == "winery" and allowed_view:
        owner_winery_id = int(allowed_view[0])
        if winery_id and int(winery_id) != owner_winery_id:
            raise HTTPException(403, "Forbidden")
        winery_id = owner_winery_id

    if not allowed_view:
        return HTMLResponse(page(
            title="QRFACILE · Nuovo lotto",
            subtitle="Nuovo lotto",
            body_html="""
            <section class="newWineWrap">
              <div class="card">
                <div class="h2">Nessuna cantina disponibile</div>
                <div class="p">Non risultano cantine collegate a questo account.</div>
              </div>
            </section>
            """,
            role=role,
            user_email=user.get("email", ""),
            credits={"wine": 0, "generic": 0},
        ), status_code=200)

    selected_winery = None
    wine_masters = []
    studios = []
    balances = {"wine": 0, "generic": 0}

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            balances = _balances(cur, uid)

            if winery_id:
                if int(winery_id) not in allowed_view:
                    raise HTTPException(403, "Forbidden")

                selected_winery = _winery(cur, int(winery_id))

                try:
                    cur.execute(
                        """
                        SELECT id, name
                        FROM wines_master
                        WHERE winery_id=%s
                        ORDER BY lower(name)
                        LIMIT 800
                        """,
                        (int(winery_id),),
                    )
                    wine_masters = cur.fetchall() or []
                except Exception:
                    wine_masters = []

                studios = _connected_studios(cur, int(winery_id))

            cur.execute(
                """
                SELECT id AS winery_id, name
                FROM wineries
                WHERE id = ANY(%s)
                ORDER BY lower(name)
                """,
                (allowed_view,),
            )
            wineries = cur.fetchall() or []

    opts = []
    sel_wid = int(selected_winery["winery_id"]) if selected_winery else 0

    if role in ("studio", "admin") and not sel_wid:
        opts.append("<option value='0' selected>— Seleziona cantina —</option>")

    for w in wineries:
        wid = int(w["winery_id"])
        selected = "selected" if sel_wid and wid == sel_wid else ""
        opts.append(
            f"<option value='{wid}' {selected}>{esc(w.get('name') or '')}</option>"
        )

    selected_master_id = int(wine_master_id or 0)
    master_ids = {int(wm["id"]) for wm in (wine_masters or [])}
    keep_master_selection = selected_master_id in master_ids
    master_placeholder_selected = "" if keep_master_selection else "selected"
    master_opts = [f"<option value='0' {master_placeholder_selected}>— Seleziona etichetta esistente —</option>"]

    for wm in (wine_masters or []):
        mid = int(wm["id"])
        selected = "selected" if keep_master_selection and selected_master_id == mid else ""
        master_opts.append(
            f"<option value='{mid}' {selected}>{esc(wm.get('name') or '')}</option>"
        )

    if role == "winery" and selected_winery:
        winery_field_html = f"""
            <div class="readonlyField">
              <div class="readonlyLabel">Cantina</div>
              <div class="readonlyValue">{esc(selected_winery.get('name') or '')}</div>
              <input type="hidden" name="winery_id" value="{sel_wid}">
            </div>
            <div class="note" style="margin-top:10px">
              La cantina è collegata automaticamente al tuo account.
            </div>
        """
    else:
        winery_field_html = f"""
            <label>Cantina</label>
            <select name="winery_id" required onchange="newWineReloadForWinery(this)">
              {''.join(opts)}
            </select>
            <div class="note" style="margin-top:10px">
              Se non hai permesso <b>create</b>, il salvataggio verrà bloccato.
            </div>
        """

    subtitle = "Crea nuovo lotto vino"
    winery_hint = "Seleziona la cantina, scegli una etichetta esistente e compila i dati principali del lotto."

    if selected_winery:
        subtitle = f"Nuovo lotto per {esc(selected_winery.get('name') or '')}"
        winery_hint = "La cantina è già preselezionata. Scegli una etichetta/prodotto esistente a cui collegare il lotto."

    actions = (
        pill(f"wine: {balances.get('wine', 0)}", "green") + " " +
        pill(f"generic: {balances.get('generic', 0)}") + " " +
        top_actions(
            ("/app/start", "Menu"),
            ("/app/dashboard", "Dashboard"),
            ("/app/new-wine-master", "Nuova etichetta"),
            ("/app/billing", "Crediti"),
            ("/logout", "Logout"),
        )
    )

    msg_html = ""
    if msg:
        msg_html = f"""
        <div class="note note-ok" style="margin-top:18px">
          <b>OK:</b> {esc(msg)}
        </div>
        """

    has_master_options = bool(wine_masters)
    no_master_html = ""
    create_disabled = ""
    if selected_winery and not has_master_options:
        create_disabled = "disabled"
        no_master_html = """
        <div class="note" style="margin-top:16px">
          Prima di creare un lotto devi creare almeno una <b>etichetta/prodotto</b>.
          Il lotto verrà collegato all’etichetta selezionata e genererà il QR definitivo.
          <div style="margin-top:12px">
            <a class="btn btn-primary" href="/app/new-wine-master">Crea nuova etichetta</a>
          </div>
        </div>
        """

    studio_select_html = ""
    if role in ("winery", "admin") and selected_winery:
        studio_select_html = _studio_assignment_box(
            section_no=3,
            studios=studios,
            invite_enabled=True,
            context="Puoi invitare subito uno studio o scegliere uno studio collegato; l'assegnazione operativa resta sulla singola etichetta.",
        )

    body = f"""
    <section class="newWineWrap">
      <div class="newWineHero">
        <div>
          <div class="newWineEyebrow">Lotti QR</div>
          <div class="h1">{subtitle}</div>
          <div class="p">
            Crea un lotto collegandolo a una etichetta/prodotto esistente.
            La creazione genera il QR definitivo e scala <b>1 credito wine</b> per QR 10 anni oppure <b>2 crediti wine</b> per QR 25 anni.
          </div>
          {msg_html}
        </div>

        <div class="newWineHeroCard">
          <div class="newWineHeroCardTitle">Crediti richiesti</div>
          <div class="newWineCreditValue">1/2</div>
          <div class="newWineHeroCardText">1 credito per 10 anni · 2 crediti per 25 anni</div>
        </div>
      </div>

      <form class="card newWineForm" method="post" action="/app/new-wine">
        <div class="newWineSectionTitle">
          <span>1</span>
          <div>
            <b>Cantina ed etichetta</b>
            <small>{winery_hint}</small>
          </div>
        </div>

        <div class="newWineGrid2">
          <div>
            {winery_field_html}
          </div>

          <div>
            <label>Etichetta esistente</label>
            <select name="wine_master_id">
              {''.join(master_opts)}
            </select>
            <div class="note" style="margin-top:10px">
              Seleziona l’etichetta/prodotto a cui collegare questo lotto.
              Se non esiste ancora, creala da
              <a class="dashboardInlineLink" href="/app/new-wine-master">Nuova etichetta</a>.
            </div>
          </div>
        </div>

        <div class="newWineSectionTitle" style="margin-top:24px">
          <span>2</span>
          <div>
            <b>Dati lotto</b>
            <small>Compila i dati principali. Potrai completare compliance e immagini dopo la creazione.</small>
          </div>
        </div>

        <div class="newWineGrid3">
          <div style="grid-column:1 / -1">
            <label>Etichetta selezionata</label>
            <input class="input" name="wine_name" placeholder="Compilata automaticamente dall’etichetta scelta" readonly>
          </div>

          <div>
            <label>Annata opzionale</label>
            <input class="input" name="vintage" placeholder="2023">
          </div>

          <div>
            <label>Lotto opzionale</label>
            <input class="input" name="lot" placeholder="L001/7">
          </div>

          <div>
            <label>Volume ml</label>
            <input class="input" name="volume_ml" value="750" inputmode="numeric">
          </div>

          <div>
            <label>Grado alcolico opzionale</label>
            <input class="input" name="alcohol" placeholder="13.5">
          </div>

          <div>
            <label>Durata QR vino</label>
            <select name="qr_duration_years">
              <option value="10" selected>10 anni · 1 credito wine</option>
              <option value="25">25 anni · 2 crediti wine</option>
            </select>
            <div class="note" style="margin-top:10px">
              Puoi creare un QR standard da 10 anni oppure un QR esteso da 25 anni.
            </div>
          </div>
        </div>

        {no_master_html}
        {studio_select_html}

        <div class="newWineActions">
          <button class="btn btn-primary" type="submit" {create_disabled}>Crea lotto + QR</button>
          <a class="btn" href="/app/dashboard">Torna alla dashboard</a>
        </div>

        <div class="note" style="margin-top:16px">
          Dopo la creazione entrerai nella scheda del lotto, dove potrai caricare immagini,
          completare i dati obbligatori, gestire la compliance ed esportare il QR.
        </div>
      </form>

      <style>
        .newWineWrap {{
          max-width:1180px;
          margin:0 auto;
        }}

        .newWineHero {{
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
          grid-template-columns:minmax(0,1.4fr) 260px;
          gap:24px;
          align-items:end;
        }}

        .newWineEyebrow {{
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

        .newWineHeroCard {{
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.72);
          border-radius:24px;
          padding:18px;
          box-shadow:0 18px 45px rgba(2,8,23,.06);
        }}

        .newWineHeroCardTitle {{
          color:#64748b;
          font-size:12px;
          font-weight:950;
          letter-spacing:.08em;
          text-transform:uppercase;
        }}

        .newWineCreditValue {{
          margin-top:10px;
          font-size:46px;
          line-height:1;
          font-weight:950;
        }}

        .newWineHeroCardText {{
          margin-top:8px;
          color:#64748b;
          font-size:13px;
          font-weight:800;
          line-height:1.35;
        }}

        .newWineForm {{
          margin-top:18px;
          padding:26px;
        }}

        .readonlyField {{
          border:1px solid rgba(2,8,23,.10);
          border-radius:14px;
          background:rgba(248,250,252,.92);
          padding:13px 14px;
          min-height:48px;
        }}

        .readonlyLabel {{
          color:#64748b;
          font-size:12px;
          font-weight:900;
          line-height:1.2;
        }}

        .readonlyValue {{
          margin-top:4px;
          color:#0f172a;
          font-weight:950;
          line-height:1.25;
        }}

        .newWineSectionTitle {{
          display:flex;
          gap:12px;
          align-items:flex-start;
          margin-bottom:14px;
        }}

        .newWineSectionTitle span {{
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

        .newWineSectionTitle b {{
          display:block;
          font-size:17px;
          font-weight:950;
        }}

        .newWineSectionTitle small {{
          display:block;
          margin-top:3px;
          color:#64748b;
          font-weight:750;
          line-height:1.35;
        }}

        .newWineGrid2 {{
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:16px;
        }}

        .newWineGrid3 {{
          display:grid;
          grid-template-columns:1fr 1fr 1fr;
          gap:16px;
        }}

        .newWineActions {{
          margin-top:22px;
          display:flex;
          gap:12px;
          flex-wrap:wrap;
        }}

        .newWineWorkBox {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:18px;
          background:rgba(248,250,252,.72);
          padding:16px;
          display:grid;
          gap:12px;
        }}

        .newWineWorkOption {{
          display:flex;
          gap:12px;
          align-items:flex-start;
          border:1px solid rgba(2,8,23,.08);
          border-radius:14px;
          background:white;
          padding:13px 14px;
          cursor:pointer;
        }}

        .newWineWorkOption input {{
          margin-top:4px;
        }}

        .newWineWorkOption b,
        .newWineWorkOption small {{
          display:block;
        }}

        .newWineWorkOption small {{
          margin-top:3px;
          color:#64748b;
          line-height:1.35;
        }}

        .newWineWorkNested {{
          padding:0 4px 4px 30px;
        }}

        .dashboardInlineLink {{
          display:inline-flex;
          padding:5px 8px;
          border-radius:999px;
          background:rgba(236,253,245,.70);
          border:1px solid rgba(20,184,166,.12);
          font-size:12px;
          font-weight:900;
          color:#0f766e;
        }}

        @media(max-width:950px) {{
          .newWineHero {{
            grid-template-columns:1fr;
          }}

          .newWineGrid2,
          .newWineGrid3 {{
            grid-template-columns:1fr;
          }}
        }}

        @media(max-width:560px) {{
          .newWineHero,
          .newWineForm {{
            padding:22px;
          }}

          .newWineActions .btn {{
            width:100%;
          }}
        }}
      </style>

      <script>
        function newWineReloadForWinery(selectEl) {{
          var wineryId = selectEl && selectEl.value ? selectEl.value : "0";
          if (!wineryId || wineryId === "0") return;

          var url = new URL("/app/new-wine", window.location.origin);
          url.searchParams.set("winery_id", wineryId);

          var form = selectEl.form;
          if (form) {{
            var master = form.querySelector('select[name="wine_master_id"]');
            if (master && master.value && master.value !== "0") {{
              url.searchParams.set("wine_master_id", master.value);
            }}
          }}

          window.location.href = url.toString();
        }}
      </script>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Nuovo lotto",
        subtitle="Nuovo lotto",
        body_html=body,
        actions_html=actions,
        msg="",
        err=err,
        user_email=user.get("email", ""),
        role=role,
        credits=balances,
    ))



def _subscription_gate_for_new_wine(cur, user: dict, owner_user_id: int, winery_id: int) -> tuple[bool, str]:
    """
    Regola:
    - admin: può creare sempre.
    - se non esiste subscription active: non blocca qui; decide il saldo crediti.
      Questo permette l'uso dei 3 crediti QR vino gratuiti iniziali.
    - se esiste subscription active ma scaduta: blocca nuovi QR.
    - se subscription active valida: ok.
    """
    role = (user.get("role") or "").lower().strip()

    if role == "admin":
        return True, ""

    cur.execute(
        """
        SELECT plan, expires_at
        FROM subscriptions
        WHERE user_id=%s
          AND COALESCE(winery_id, 0)=COALESCE(%s, 0)
          AND status='active'
        ORDER BY expires_at DESC
        LIMIT 1
        """,
        (int(owner_user_id), int(winery_id) if winery_id else None),
    )
    sub = cur.fetchone()

    if not sub:
        return True, ""

    expires_at = int(sub.get("expires_at") or 0)

    if expires_at and expires_at < now():
        return False, "Piano scaduto: rinnova il piano per creare nuovi QR vino."

    return True, ""



@router.post("/app/new-wine")
def new_wine_post(
    request: Request,
    winery_id: int = Form(...),
    wine_master_id: int = Form(0),
    wine_name: str = Form(""),
    vintage: str = Form(""),
    lot: str = Form(""),
    volume_ml: str = Form("750"),
    alcohol: str = Form(""),
    qr_duration_years: int = Form(10),
    studio_work_mode: str = Form("self"),
    invite_studio_email: str = Form(""),
):
    user = require_any_role(request, ("winery", "studio", "admin"))

    require_any_role(
        request,
        ("winery", "studio", "admin"),
        winery_id=int(winery_id),
        need="create",
    )

    wine_master_id = int(wine_master_id or 0)

    vintage = (vintage or "").strip()[:20] or None
    lot = (lot or "").strip()[:60] or None
    alcohol = (alcohol or "").strip()[:20] or None

    try:
        vol = int(str(volume_ml or "750").strip() or "750")
        if vol <= 0 or vol > 5000:
            vol = 750
    except Exception:
        vol = 750

    try:
        duration_years = int(qr_duration_years or 10)
    except Exception:
        duration_years = 10

    if duration_years not in (10, 25):
        duration_years = 10

    credit_cost = 2 if duration_years == 25 else 1

    ts = now()
    expires_at = ts + (60 * 60 * 24 * 365 * duration_years)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _winery(cur, int(winery_id))
            owner_user_id = int(w["owner_user_id"])

            if wine_master_id > 0:
                cur.execute(
                    """
                    SELECT id, name
                    FROM wines_master
                    WHERE id=%s AND winery_id=%s
                    LIMIT 1
                    """,
                    (wine_master_id, int(winery_id)),
                )
                wm = cur.fetchone()

                if not wm:
                    conn.rollback()
                    return RedirectResponse(
                        "/app/new-wine?msg=Vino%20master%20non%20valido",
                        status_code=303,
                    )

                wine_name_final = (wm.get("name") or "").strip()
                wine_master_id = int(wm["id"])

            else:
                conn.rollback()
                return RedirectResponse(
                    f"/app/new-wine?winery_id={int(winery_id)}&err=Seleziona%20prima%20una%20etichetta%20esistente",
                    status_code=303,
                )

            sub_ok, sub_msg = _subscription_gate_for_new_wine(
                cur,
                user,
                owner_user_id,
                int(winery_id),
            )

            if not sub_ok:
                conn.rollback()
                return RedirectResponse(
                    url="/app/billing?err=Piano%20scaduto%3A%20rinnova%20per%20creare%20nuovi%20QR%20vino",
                    status_code=303,
                )

            cur.execute(
                """
                SELECT COALESCE(SUM(delta), 0) AS balance
                FROM credit_ledger
                WHERE user_id=%s AND credit_type='wine'
                """,
                (owner_user_id,),
            )
            balance_wine = int((cur.fetchone() or {}).get("balance") or 0)

            if balance_wine < credit_cost:
                conn.rollback()
                return RedirectResponse(
                    url="/app/billing?err=Crediti%20wine%20insufficienti%3A%20acquista%20o%20rinnova%20un%20piano",
                    status_code=303,
                )

            slug = new_slug()
            public_path = f"/e/{slug}"

            cur.execute(
                """
                INSERT INTO qr_items(
                  owner_user_id, winery_id, qr_type, status, slug, title,
                  has_back, public_path, payload, created_at, updated_at
                )
                VALUES (%s,%s,'cantina','bozza',%s,%s,1,%s,'{}'::jsonb,%s,%s)
                RETURNING id
                """,
                (
                    owner_user_id,
                    int(winery_id),
                    slug,
                    wine_name_final,
                    public_path,
                    ts,
                    ts,
                ),
            )
            qr_item_id = int(cur.fetchone()["id"])

            cols = _columns(cur, "qr_wines")
            base_cols = [
                "qr_item_id",
                "winery_id",
                "wine_name",
                "expires_at",
                "created_at",
                "updated_at",
            ]

            if not set(base_cols) <= cols:
                raise HTTPException(500, "Schema qr_wines non compatibile")

            col_names = [
                "qr_item_id",
                "winery_id",
                "wine_name",
                "expires_at",
                "created_at",
                "updated_at",
            ]
            values = [
                qr_item_id,
                int(winery_id),
                wine_name_final,
                expires_at,
                ts,
                ts,
            ]

            if "wine_master_id" in cols:
                col_names.append("wine_master_id")
                values.append(wine_master_id if wine_master_id > 0 else None)

            if "qr_duration_years" in cols:
                col_names.append("qr_duration_years")
                values.append(duration_years)

            if "vintage" in cols:
                col_names.append("vintage")
                values.append(vintage)

            if "lot" in cols:
                col_names.append("lot")
                values.append(lot)

            if "volume_ml" in cols:
                col_names.append("volume_ml")
                values.append(vol)

            if "alcohol" in cols:
                col_names.append("alcohol")
                values.append(alcohol)

            placeholders = ",".join(["%s"] * len(values))
            cols_sql = ",".join(col_names)

            try:
                cur.execute(
                    f"INSERT INTO qr_wines({cols_sql}) VALUES ({placeholders}) RETURNING id",
                    tuple(values),
                )
            except UniqueViolation as exc:
                conn.rollback()
                if exc.diag.constraint_name == QR_WINES_QR_ITEM_UNIQUE_CONSTRAINT:
                    return RedirectResponse(
                        url=(
                            f"/app/new-wine?winery_id={int(winery_id)}"
                            "&err=Esiste%20gi%C3%A0%20un%20vino%20per%20questo%20QR"
                        ),
                        status_code=303,
                    )
                raise
            wine_id = int(cur.fetchone()["id"])

            cur.execute(
                """
                INSERT INTO credit_ledger
                  (user_id, credit_type, delta, reason, ref_table, ref_id, created_at)
                VALUES
                  (%s, 'wine', %s, 'wine_lot_create', 'qr_wines', %s, %s)
                """,
                (owner_user_id, -credit_cost, wine_id, ts),
            )

            if (studio_work_mode or "").strip().lower() == "invite":
                _create_studio_invite_for_context(
                    cur,
                    winery_id=int(winery_id),
                    inviter_user_id=int(user["id"]),
                    studio_email=invite_studio_email,
                    wine_id=int(wine_id),
                )

            conn.commit()

    return RedirectResponse(f"/app/wine/{wine_id}", status_code=303)


# ============================================================
# NEW LABEL
# ============================================================

@router.get("/app/new-label", response_class=HTMLResponse)
def new_label_get(request: Request, msg: str = "", wine_id: int = 0):
    user = require_any_role(request, ("winery", "studio", "admin"))

    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    allowed = _allowed_winery_ids(user, need="view")

    if not allowed:
        return HTMLResponse(page(
            title="QRFACILE · Nuova etichetta",
            subtitle="Nuova etichetta",
            body_html="""
            <section class="newWineWrap">
              <div class="card">
                <div class="h2">Nessuna cantina disponibile</div>
                <div class="p">Non risultano cantine collegate a questo account.</div>
              </div>
            </section>
            """,
            role=role,
            user_email=user.get("email", ""),
            credits={"wine": 0, "generic": 0},
        ), status_code=200)

    selected_wine = None
    filter_winery = None
    auto_assign_note = ""
    studios = []
    balances = {"wine": 0, "generic": 0}

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            balances = _balances(cur, uid)

            if wine_id:
                selected_wine = _wine(cur, int(wine_id))

                if int(selected_wine["winery_id"]) not in allowed:
                    raise HTTPException(403, "Forbidden")

                filter_winery = int(selected_wine["winery_id"])

            if filter_winery:
                cur.execute(
                    """
                    SELECT qw.id AS wine_id, qw.wine_name, qw.vintage, qw.lot,
                           qw.winery_id, w.name AS winery_name
                    FROM qr_wines qw
                    JOIN wineries w ON w.id = qw.winery_id
                    WHERE qw.winery_id=%s
                    ORDER BY lower(qw.wine_name), qw.id DESC
                    LIMIT 400
                    """,
                    (filter_winery,),
                )
            else:
                cur.execute(
                    """
                    SELECT qw.id AS wine_id, qw.wine_name, qw.vintage, qw.lot,
                           qw.winery_id, w.name AS winery_name
                    FROM qr_wines qw
                    JOIN wineries w ON w.id = qw.winery_id
                    WHERE qw.winery_id = ANY(%s)
                    ORDER BY w.name, lower(qw.wine_name), qw.id DESC
                    LIMIT 400
                    """,
                    (allowed,),
                )

            wines = cur.fetchall() or []

            if filter_winery:
                studios = _connected_studios(cur, int(filter_winery))

                if len(studios) == 1:
                    who = (
                        (studios[0].get("company_name") or "").strip()
                        or (studios[0].get("email") or "Studio")
                    )
                    auto_assign_note = f"""
                    <div class="note" style="margin-top:16px">
                      Questa cantina ha un solo studio collegato: <b>{esc(who)}</b>.<br>
                      La nuova etichetta verrà assegnata automaticamente a questo studio.
                    </div>
                    """
                elif len(studios) > 1:
                    auto_assign_note = """
                    <div class="note" style="margin-top:16px">
                      Questa cantina ha più studi collegati: scegli subito lo studio grafico da assegnare a questa etichetta.
                    </div>
                    """

    options = []
    sel_id = int(selected_wine["wine_id"]) if selected_wine else 0

    for w in wines:
        wid = int(w["wine_id"])
        label = f"{w.get('winery_name','-')} · {w.get('wine_name','-')}"

        if w.get("vintage"):
            label += f" ({w.get('vintage')})"

        if w.get("lot"):
            label += f" · lotto {w.get('lot')}"

        selected = "selected" if sel_id and wid == sel_id else ""
        options.append(f"<option value='{wid}' {selected}>{esc(label)}</option>")

    subtitle = "Crea nuova etichetta"

    if selected_wine:
        subtitle = f"Etichetta per {esc(selected_wine.get('wine_name') or '')}"

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

    msg_html = ""
    if msg:
        msg_html = f"""
        <div class="note note-ok" style="margin-top:18px">
          <b>OK:</b> {esc(msg)}
        </div>
        """
    studio_select_html = ""
    if role in ("winery", "admin") and filter_winery:
        studio_select_html = _studio_assignment_box(
            section_no=3,
            studios=studios,
            invite_enabled=True,
            context="Decidi subito chi lavora su questa etichetta. Puoi cambiare studio dalla scheda etichetta.",
        )

    body = f"""
    <section class="newWineWrap">
      <div class="newWineHero">
        <div>
          <div class="newWineEyebrow">Etichette</div>
          <div class="h1">{subtitle}</div>
          <div class="p">
            Seleziona un lotto e crea una nuova etichetta fronte o retro.
            Lo studio deve avere permesso <b>create</b>.
          </div>
          {msg_html}
          {auto_assign_note}
        </div>

        <div class="newWineHeroCard">
          <div class="newWineHeroCardTitle">Governance</div>
          <div class="newWineCreditValue">✓</div>
          <div class="newWineHeroCardText">
            Pubblicazione sempre sotto controllo cantina/admin.
          </div>
        </div>
      </div>

      <form class="card newWineForm" method="post" action="/app/new-label/create">
        <div class="newWineSectionTitle">
          <span>1</span>
          <div>
            <b>Lotto di riferimento</b>
            <small>Scegli il lotto a cui collegare la nuova etichetta.</small>
          </div>
        </div>

        <label>Lotto</label>
        <select name="wine_id" required>
          {''.join(options) if options else "<option value=''>Nessun lotto disponibile</option>"}
        </select>

        <div class="newWineSectionTitle" style="margin-top:24px">
          <span>2</span>
          <div>
            <b>Tipo etichetta</b>
            <small>Imposta lato, lingua e nome interno facoltativo.</small>
          </div>
        </div>

        <div class="newWineGrid3">
          <div>
            <label>Tipo etichetta</label>
            <select name="label_type">
              <option value="front">Fronte</option>
              <option value="back">Retro</option>
            </select>
          </div>

          <div>
            <label>Lingua</label>
            <select name="language">
              <option value="it">Italiano</option>
              <option value="en">English</option>
              <option value="de">Deutsch</option>
              <option value="fr">Français</option>
              <option value="es">Español</option>
            </select>
          </div>

          <div>
            <label>Nome interno opzionale</label>
            <input class="input" name="title_override" placeholder="es. Back export UK">
          </div>
        </div>

        {studio_select_html}

        <div class="newWineActions">
          <button class="btn btn-primary" type="submit">Crea etichetta</button>
          <a class="btn" href="/app/labels/search">Vai alla ricerca</a>
        </div>

        <div class="note" style="margin-top:16px">
          Regola: <b>pubblicazione sempre cantina/admin</b>. Lo studio può preparare file e immagini.
        </div>
      </form>

      <style>
        .newWineWrap {{
          max-width:1180px;
          margin:0 auto;
        }}

        .newWineHero {{
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
          grid-template-columns:minmax(0,1.4fr) 260px;
          gap:24px;
          align-items:end;
        }}

        .newWineEyebrow {{
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

        .newWineHeroCard {{
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.72);
          border-radius:24px;
          padding:18px;
          box-shadow:0 18px 45px rgba(2,8,23,.06);
        }}

        .newWineHeroCardTitle {{
          color:#64748b;
          font-size:12px;
          font-weight:950;
          letter-spacing:.08em;
          text-transform:uppercase;
        }}

        .newWineCreditValue {{
          margin-top:10px;
          font-size:46px;
          line-height:1;
          font-weight:950;
        }}

        .newWineHeroCardText {{
          margin-top:8px;
          color:#64748b;
          font-size:13px;
          font-weight:800;
          line-height:1.35;
        }}

        .newWineForm {{
          margin-top:18px;
          padding:26px;
        }}

        .newWineSectionTitle {{
          display:flex;
          gap:12px;
          align-items:flex-start;
          margin-bottom:14px;
        }}

        .newWineSectionTitle span {{
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

        .newWineSectionTitle b {{
          display:block;
          font-size:17px;
          font-weight:950;
        }}

        .newWineSectionTitle small {{
          display:block;
          margin-top:3px;
          color:#64748b;
          font-weight:750;
          line-height:1.35;
        }}

        .newWineGrid2 {{
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:16px;
        }}

        .newWineGrid3 {{
          display:grid;
          grid-template-columns:1fr 1fr 1fr;
          gap:16px;
        }}

        .newWineActions {{
          margin-top:22px;
          display:flex;
          gap:12px;
          flex-wrap:wrap;
        }}

        .newWineWorkBox {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:18px;
          background:rgba(248,250,252,.72);
          padding:16px;
          display:grid;
          gap:12px;
        }}

        .newWineWorkOption {{
          display:flex;
          gap:12px;
          align-items:flex-start;
          border:1px solid rgba(2,8,23,.08);
          border-radius:14px;
          background:white;
          padding:13px 14px;
          cursor:pointer;
        }}

        .newWineWorkOption input {{
          margin-top:4px;
        }}

        .newWineWorkOption b,
        .newWineWorkOption small {{
          display:block;
        }}

        .newWineWorkOption small {{
          margin-top:3px;
          color:#64748b;
          line-height:1.35;
        }}

        .newWineWorkNested {{
          padding:0 4px 4px 30px;
        }}

        @media(max-width:950px) {{
          .newWineHero {{
            grid-template-columns:1fr;
          }}

          .newWineGrid2,
          .newWineGrid3 {{
            grid-template-columns:1fr;
          }}
        }}

        @media(max-width:560px) {{
          .newWineHero,
          .newWineForm {{
            padding:22px;
          }}

          .newWineActions .btn {{
            width:100%;
          }}
        }}
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Nuova etichetta",
        subtitle="Nuova etichetta",
        body_html=body,
        actions_html=actions,
        msg="",
        err="",
        user_email=user.get("email", ""),
        role=role,
        credits=balances,
    ))


@router.post("/app/new-label/create")
def new_label_create(
    request: Request,
    wine_id: int = Form(...),
    label_type: str = Form("front"),
    language: str = Form("it"),
    title_override: str = Form(""),
    studio_work_mode: str = Form("self"),
    assigned_studio_user_id: int = Form(0),
    invite_studio_email: str = Form(""),
):
    user = require_any_role(request, ("winery", "studio", "admin"))

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            wine = _wine(cur, int(wine_id))

    require_any_role(
        request,
        ("winery", "studio", "admin"),
        winery_id=int(wine["winery_id"]),
        need="create",
    )

    lt = (label_type or "front").strip().lower()

    if lt not in ("front", "back"):
        lt = "front"

    lang = (language or "it").strip().lower()

    if len(lang) > 5:
        lang = "it"

    tovr = (title_override or "").strip()[:120] or None
    ts = now()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO wine_labels
                  (wine_id, winery_id, qr_item_id, label_type, language, title_override,
                   active, public_enabled, created_at, updated_at, created_by_user_id)
                VALUES
                  (%s,%s,%s,%s,%s,%s, TRUE, FALSE, %s, %s, %s)
                RETURNING id
                """,
                (
                    int(wine["wine_id"]),
                    int(wine["winery_id"]),
                    int(wine["qr_item_id"]),
                    lt,
                    lang,
                    tovr,
                    ts,
                    ts,
                    int(user["id"]),
                ),
            )
            label_id = int(cur.fetchone()["id"])

            # Assegnazione studio semplificata:
            # - se crea uno studio, assegniamo lo studio stesso;
            # - se cantina/admin sceglie uno studio dal menu, assegniamo quello;
            # - altrimenti auto-assegniamo solo se la cantina ha un unico studio collegato.
            role = (user.get("role") or "").lower().strip()

            work_mode = (studio_work_mode or "self").strip().lower()

            if role == "studio":
                _assign_connected_studio_to_label(
                    cur,
                    int(label_id),
                    int(wine["winery_id"]),
                    int(user["id"]),
                )
            elif work_mode == "connected" and int(assigned_studio_user_id or 0) > 0:
                _assign_connected_studio_to_label(
                    cur,
                    int(label_id),
                    int(wine["winery_id"]),
                    int(assigned_studio_user_id),
                )
            elif work_mode == "invite":
                _create_studio_invite_for_context(
                    cur,
                    winery_id=int(wine["winery_id"]),
                    inviter_user_id=int(user["id"]),
                    studio_email=invite_studio_email,
                    wine_id=int(wine["wine_id"]),
                    label_id=int(label_id),
                )
            else:
                _auto_assign_single_connected_studio(
                    cur,
                    int(label_id),
                    int(wine["winery_id"]),
                )

            conn.commit()

    return RedirectResponse(f"/app/label/{label_id}", status_code=303)
