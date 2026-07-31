# /opt/qrfacile/qrfacile_app/dashboard_ui.py

import html

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.ui_shell import page, top_actions, esc
from qrfacile_app.ui_layout import pill

router = APIRouter()


def _h(s: str) -> str:
    return html.escape(s or "")


def _thumb(asset_path: str | None) -> str:
    if asset_path:
        return f"/uploads/{asset_path}"
    return "/static/img/placeholder_label.svg"


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


def _admin_active_winery_id(cur, user_id: int) -> int | None:
    cur.execute(
        "SELECT admin_active_winery_id FROM users WHERE id=%s LIMIT 1",
        (int(user_id),),
    )
    r = cur.fetchone() or {}
    return int(r["admin_active_winery_id"]) if r.get("admin_active_winery_id") else None


def _admin_active_winery_name(cur, winery_id: int) -> str:
    cur.execute(
        "SELECT name FROM wineries WHERE id=%s LIMIT 1",
        (int(winery_id),),
    )
    r = cur.fetchone() or {}
    return (r.get("name") or "").strip()


def _load_inline_management(cur, wine_ids: list[int], winery_ids: list[int]) -> tuple[dict[int, list[dict]], dict[int, list[dict]]]:
    labels_by_wine = {int(wine_id): [] for wine_id in wine_ids}
    studios_by_winery = {int(winery_id): [] for winery_id in winery_ids}

    if wine_ids:
        cur.execute(
            """
            SELECT
              wl.id AS label_id,
              wl.wine_id,
              wl.winery_id,
              active_lc.collaborator_user_id AS active_studio_user_id
            FROM wine_labels wl
            LEFT JOIN LATERAL (
              SELECT collaborator_user_id
              FROM label_collaborators
              WHERE wine_label_id=wl.id
                AND active=TRUE
                AND can_view=TRUE
              ORDER BY updated_at DESC NULLS LAST, id DESC
              LIMIT 1
            ) active_lc ON TRUE
            WHERE wl.wine_id = ANY(%s)
            ORDER BY wl.wine_id, wl.id
            """,
            (wine_ids,),
        )
        for row in cur.fetchall() or []:
            labels_by_wine.setdefault(int(row["wine_id"]), []).append(row)

    if winery_ids:
        cur.execute(
            """
            SELECT
              sc.winery_id,
              u.id AS studio_user_id,
              u.email,
              COALESCE(s.company_name, '') AS company_name
            FROM studio_clients sc
            JOIN users u ON u.id = sc.studio_user_id
            LEFT JOIN studios s ON s.user_id = u.id
            WHERE sc.winery_id = ANY(%s)
              AND sc.can_view=TRUE
              AND lower(u.role)='studio'
            ORDER BY sc.winery_id, lower(COALESCE(NULLIF(s.company_name, ''), u.email))
            """,
            (winery_ids,),
        )
        for row in cur.fetchall() or []:
            studios_by_winery.setdefault(int(row["winery_id"]), []).append(row)

    return labels_by_wine, studios_by_winery


def _wine_management_active_id(labels: list[dict]) -> int:
    active_ids = {int(label.get("active_studio_user_id") or 0) for label in labels if int(label.get("active_studio_user_id") or 0) > 0}
    if labels and len(active_ids) == 1 and all(int(label.get("active_studio_user_id") or 0) in active_ids for label in labels):
        return active_ids.pop()
    return 0


def _management_picker(wine_id: int, labels: list[dict], studios: list[dict], return_to: str) -> str:
    active_id = _wine_management_active_id(labels)
    options = [f"<option value='self' {'selected' if active_id <= 0 else ''}>Gestisco io</option>"]
    for studio in studios:
        sid = int(studio["studio_user_id"])
        studio_name = (studio.get("company_name") or studio.get("email") or f"Studio {sid}").strip()
        selected = "selected" if sid == active_id else ""
        options.append(f"<option value='studio:{sid}' {selected}>{_h(studio_name)}</option>")
    options.append("<option value='invite'>+ Invita nuovo Studio</option>")

    return f"""
    <form method="post" action="/app/wine/{int(wine_id)}/management/set" class="dashboardManagementPicker">
      <input type="hidden" name="return_to" value="{_h(return_to)}">
      <span>Gestione grafica</span>
      <select name="management_value">
        {''.join(options)}
      </select>
      <button class="btn" type="submit">Salva</button>
    </form>
    """


def _inline_management_controls(r: dict, role: str, labels_by_wine: dict[int, list[dict]], studios_by_winery: dict[int, list[dict]]) -> str:
    if role not in ("winery", "admin"):
        return ""

    wine_id = int(r["wine_id"])
    labels = labels_by_wine.get(wine_id, [])
    if not labels:
        return ""

    winery_id = int(r.get("winery_id") or 0)
    studios = studios_by_winery.get(winery_id, [])
    return_to = f"/app/dashboard#wine-{wine_id}"
    return f"""
    <div class="dashboardManagementPickers" onclick="event.stopPropagation()">
      {_management_picker(wine_id, labels, studios, return_to)}
    </div>
    """


def _status_badge(status: str) -> str:
    status = (status or "").strip().lower()

    if status == "attiva":
        return pill("Attivo", "green")

    if status in ("bozza", "draft"):
        return pill("Bozza", "warn")

    if status:
        return pill(status.capitalize(), "muted")

    return pill("Bozza", "warn")


def _compliance_state(r: dict) -> tuple[str, list[str], list[str]]:
    """
    Semaforo leggero da dashboard.
    Non modifica nulla, non scrive su DB.
    Usa solo i dati già presenti nelle tabelle operative.
    """
    missing = []
    warnings = []

    wine_name = (r.get("wine_name") or "").strip()
    winery_name = (r.get("winery_name") or "").strip()
    slug = (r.get("slug") or "").strip()

    ingredient_count = int(r.get("ingredient_count") or 0)
    extra_ingredients = (r.get("extra_ingredients") or "").strip()

    allergen_count = int(r.get("allergen_count") or 0)
    has_allergen_flags = bool(r.get("contains_sulfites")) or bool(r.get("contains_egg")) or bool(r.get("contains_milk"))

    nutrition_ok = bool(r.get("nutrition_ok"))
    recycle_count = int(r.get("recycle_count") or 0)

    front_thumb = (r.get("front_thumb") or "").strip()
    back_thumb = (r.get("back_thumb") or "").strip()

    if not wine_name:
        missing.append("nome vino")

    if not winery_name:
        missing.append("cantina")

    if not slug:
        missing.append("slug pubblico")

    if ingredient_count <= 0 and not extra_ingredients:
        missing.append("ingredienti")

    if allergen_count <= 0 and not has_allergen_flags:
        missing.append("allergeni")

    if not nutrition_ok:
        missing.append("energia kJ/kcal")

    if recycle_count <= 0:
        missing.append("riciclabilità")

    if not front_thumb:
        warnings.append("fronte etichetta")

    if not back_thumb:
        warnings.append("retro etichetta")

    if missing:
        return "red", missing, warnings

    if warnings:
        return "yellow", missing, warnings

    return "green", missing, warnings


def _compliance_badge_html(r: dict) -> str:
    state, missing, warnings = _compliance_state(r)

    if state == "green":
        return """
        <div class="dashboardCompliance dashboardComplianceGreen">
          <span class="dashboardComplianceDot"></span>
          <div>
            <b>Compliance OK</b>
            <small>Dati principali completi</small>
          </div>
        </div>
        """

    if state == "yellow":
        detail = ", ".join(warnings[:3])
        return f"""
        <div class="dashboardCompliance dashboardComplianceYellow">
          <span class="dashboardComplianceDot"></span>
          <div>
            <b>Quasi completo</b>
            <small>Manca: {_h(detail)}</small>
          </div>
        </div>
        """

    detail = ", ".join(missing[:4])
    return f"""
    <div class="dashboardCompliance dashboardComplianceRed">
      <span class="dashboardComplianceDot"></span>
      <div>
        <b>Da completare</b>
        <small>Manca: {_h(detail)}</small>
      </div>
    </div>
    """


def _mini_check(label: str, ok: bool) -> str:
    cls = "ok" if ok else "ko"
    mark = "✓" if ok else "!"
    return f"""
    <span class="dashboardMiniCheck {cls}">
      <b>{mark}</b>{_h(label)}
    </span>
    """


def _lot_flags(r: dict) -> dict:
    ingredient_ok = int(r.get("ingredient_count") or 0) > 0 or bool((r.get("extra_ingredients") or "").strip())
    allergen_ok = (
        int(r.get("allergen_count") or 0) > 0
        or bool(r.get("contains_sulfites"))
        or bool(r.get("contains_egg"))
        or bool(r.get("contains_milk"))
    )
    nutrition_ok = bool(r.get("nutrition_ok"))
    recycle_ok = int(r.get("recycle_count") or 0) > 0
    images_ok = bool((r.get("front_thumb") or "").strip()) and bool((r.get("back_thumb") or "").strip())
    preview_ok = bool((r.get("slug") or "").strip())
    published_ok = (r.get("status") or "").strip().lower() == "attiva"

    return {
        "ingredients": ingredient_ok,
        "allergens": allergen_ok,
        "nutrition": nutrition_ok,
        "recycle": recycle_ok,
        "images": images_ok,
        "preview": preview_ok,
        "published": published_ok,
    }


def _checks_html(r: dict) -> str:
    flags = _lot_flags(r)

    return f"""
    <div class="dashboardChecks" onclick="event.stopPropagation()">
      {_mini_check("Ingredienti", flags["ingredients"])}
      {_mini_check("Allergeni", flags["allergens"])}
      {_mini_check("Nutrizione", flags["nutrition"])}
      {_mini_check("Riciclo", flags["recycle"])}
      {_mini_check("Immagini", flags["images"])}
      {_mini_check("Preview", flags["preview"])}
      {_mini_check("Pubblicazione", flags["published"])}
    </div>
    """


def _dashboard_counts(rows: list[dict]) -> dict:
    complete = 0
    incomplete = 0
    published = 0

    for r in rows:
        state, missing, warnings = _compliance_state(r)

        if (r.get("status") or "").strip().lower() == "attiva":
            published += 1

        if state == "green" and not missing and not warnings:
            complete += 1
        else:
            incomplete += 1

    return {
        "total": len(rows),
        "complete": complete,
        "incomplete": incomplete,
        "published": published,
    }


def _onboarding_check(label: str, done: int, total: int) -> str:
    ok = total > 0 and done == total
    cls = "ok" if ok else "todo"
    mark = "✓" if ok else str(done)
    detail = "completo" if ok else f"{done}/{total} lotti"

    if total == 0:
        mark = "0"
        detail = "nessun lotto"

    return f"""
    <div class="dashboardOnboardingCheck {cls}">
      <span>{_h(mark)}</span>
      <div>
        <b>{_h(label)}</b>
        <small>{_h(detail)}</small>
      </div>
    </div>
    """


def _primary_lot_cta(r: dict, role: str) -> str:
    wine_id = int(r["wine_id"])
    slug = _h(r.get("slug") or "")
    state, missing, warnings = _compliance_state(r)
    is_published = (r.get("status") or "").strip().lower() == "attiva"

    if missing:
        return f'<a class="btn btn-primary" href="/app/wine/{wine_id}?tab=compliance">Completa compliance</a>'

    if warnings:
        return f'<a class="btn btn-primary" href="/app/wine/{wine_id}?tab=images">Completa compliance</a>'

    if is_published and slug:
        return f'<a class="btn btn-primary" href="/e/{slug}" target="_blank">Apri pagina pubblica</a>'

    if is_published:
        return f'<a class="btn btn-primary" href="/app/wine/{wine_id}?tab=export">Apri pagina pubblica</a>'

    if role in ("winery", "admin"):
        return f"""
        <form method="post" action="/app/wine/{wine_id}/publish" class="dashboardInlineForm">
          <button class="btn btn-primary" type="submit">Pubblica pagina ufficiale</button>
        </form>
        """

    return f'<a class="btn btn-primary" href="/app/wine/{wine_id}?tab=export">Pubblica pagina ufficiale</a>'


def _next_step(rows: list[dict], role: str) -> tuple[str, str, str]:
    if not rows:
        return ("Nuova etichetta", "Crea la prima etichetta/prodotto; poi potrai aggiungere i lotti collegati.", "/app/new-wine-master")

    for r in rows:
        state, missing, warnings = _compliance_state(r)
        wine_id = int(r["wine_id"])
        name = (r.get("wine_name") or "lotto").strip()

        if missing:
            return ("Completa compliance", f"Riparti da {name}: mancano dati obbligatori.", f"/app/wine/{wine_id}?tab=compliance")

        if warnings:
            return ("Completa compliance", f"Controlla immagini e dettagli di {name}.", f"/app/wine/{wine_id}?tab=images")

    for r in rows:
        if (r.get("status") or "").strip().lower() != "attiva":
            wine_id = int(r["wine_id"])
            name = (r.get("wine_name") or "lotto").strip()
            if role in ("winery", "admin"):
                return ("Pubblica pagina ufficiale", f"{name} è completo: puoi procedere alla pubblicazione.", f"/app/wine/{wine_id}?tab=export")
            return ("Preview tecnica", f"{name} è completo: verifica la preview prima della consegna.", f"/app/wine/{wine_id}?tab=export")

    first = rows[0]
    slug = (first.get("slug") or "").strip()
    if slug:
        return ("Preview tecnica", "Tutti i lotti visibili sono pronti: controlla l’esperienza finale.", f"/preview/{_h(slug)}")

    return ("Nuovo lotto", "Aggiungi un nuovo lotto quando hai una nuova etichetta da preparare.", "/app/new-wine")


def _onboarding_html(rows: list[dict], role: str) -> str:
    counts = _dashboard_counts(rows)
    total = counts["total"]
    progress = int(round((counts["complete"] / total) * 100)) if total else 0

    checklist = {
        "Ingredienti": 0,
        "Allergeni": 0,
        "Nutrizione": 0,
        "Riciclo": 0,
        "Immagini": 0,
        "Preview": 0,
        "Pubblicazione": 0,
    }

    for r in rows:
        flags = _lot_flags(r)
        checklist["Ingredienti"] += 1 if flags["ingredients"] else 0
        checklist["Allergeni"] += 1 if flags["allergens"] else 0
        checklist["Nutrizione"] += 1 if flags["nutrition"] else 0
        checklist["Riciclo"] += 1 if flags["recycle"] else 0
        checklist["Immagini"] += 1 if flags["images"] else 0
        checklist["Preview"] += 1 if flags["preview"] else 0
        checklist["Pubblicazione"] += 1 if flags["published"] else 0

    checks_html = "".join([_onboarding_check(label, done, total) for label, done in checklist.items()])
    next_label, next_text, next_href = _next_step(rows, role)

    return f"""
    <section class="dashboardOnboarding card">
      <div class="dashboardOnboardingHead">
        <div>
          <div class="dashboardSectionKicker">Percorso guidato</div>
          <div class="h2">Compliance cantina</div>
          <div class="p">
            Una vista unica per capire cosa è pronto, cosa manca e qual è la prossima azione utile.
          </div>
        </div>

        <div class="dashboardProgressBox">
          <div class="dashboardProgressLabel">
            <span>Avanzamento</span>
            <b>{progress}%</b>
          </div>
          <div class="dashboardProgressTrack">
            <span style="width:{progress}%"></span>
          </div>
        </div>
      </div>

      <div class="dashboardGlobalState">
        <div>
          <span>Lotti completi</span>
          <b>{counts["complete"]}</b>
        </div>
        <div>
          <span>Incompleti</span>
          <b>{counts["incomplete"]}</b>
        </div>
        <div>
          <span>Pubblicati</span>
          <b>{counts["published"]}</b>
        </div>
      </div>

      <div class="dashboardOnboardingGrid">
        <div class="dashboardChecklist">
          {checks_html}
        </div>

        <div class="dashboardNextStep">
          <span>Step consigliato</span>
          <b>{_h(next_label)}</b>
          <small>{_h(next_text)}</small>
          <div class="dashboardNextActions">
            <a class="btn btn-primary" href="{_h(next_href)}">{_h(next_label)}</a>
            <a class="btn" href="/app/new-wine-master">Nuova etichetta</a>
            <a class="btn" href="/app/new-wine">Nuovo lotto</a>
          </div>
        </div>
      </div>
    </section>
    """


def _wine_card(r: dict, role: str = "", labels_by_wine: dict[int, list[dict]] | None = None, studios_by_winery: dict[int, list[dict]] | None = None) -> str:
    slug = r.get("slug") or ""
    wine_id = int(r["wine_id"])

    front = _thumb(r.get("front_thumb"))
    back = _thumb(r.get("back_thumb"))

    wine_name = _h(r.get("wine_name") or "Senza nome")
    winery_name = _h(r.get("winery_name") or "")
    vintage = _h(str(r.get("vintage") or "").strip())
    lot = _h(r.get("lot") or "-")
    slug_safe = _h(slug)

    badge = _status_badge(r.get("status") or "")
    compliance = _compliance_badge_html(r)
    checks = _checks_html(r)

    vintage_html = ""
    if vintage:
        vintage_html = f"<span class='dashboardMetaPill'>Annata {vintage}</span>"

    preview_link = f"/preview/{slug_safe}" if slug_safe else "#"
    primary_cta = _primary_lot_cta(r, role)
    worker_html = _worker_summary_html(r, role)
    management_controls = _inline_management_controls(r, role, labels_by_wine or {}, studios_by_winery or {})

    return f"""
    <article id="wine-{wine_id}" class="card dashboardWineCard" onclick="window.location='/app/wine/{wine_id}'">
      <div class="dashboardWineMain">
        <div class="dashboardThumbs">
          <div class="dashboardThumbBox">
            <img src="{front}" alt="Etichetta fronte">
            <span>Fronte</span>
          </div>

          <div class="dashboardThumbBox">
            <img src="{back}" alt="Etichetta retro">
            <span>Retro</span>
          </div>
        </div>

        <div class="dashboardWineContent">
          <div class="dashboardWineTop">
            <div class="dashboardWineInfo">
              <div class="dashboardWineTitleRow">
                <h2>{wine_name}</h2>
                {badge}
              </div>

              <div class="dashboardWineryName">{winery_name}</div>

              <div class="dashboardMeta">
                {vintage_html}
                <span class="dashboardMetaPill">Lotto {lot}</span>
                <span class="dashboardMetaPill">Slug {slug_safe or "-"}</span>
              </div>

              {checks}
              {worker_html}
              {management_controls}
            </div>

            <div class="dashboardWineRight" onclick="event.stopPropagation()">
              {compliance}

              <div class="dashboardWineActions">
                <a class="btn" href="/app/wine/{wine_id}?tab=images">Immagini</a>
                <a class="btn" href="{preview_link}" target="_blank">Preview tecnica</a>
                {primary_cta}
              </div>
            </div>
          </div>

          <div class="dashboardWineFooter" onclick="event.stopPropagation()">
            <a class="dashboardInlineLink" href="/app/wine/{wine_id}?tab=compliance">
              Compliance
            </a>
            <a class="dashboardInlineLink" href="/app/wine/{wine_id}?tab=export">
              Esportazione QR
            </a>
            <a class="dashboardInlineLink" href="/app/wine/{wine_id}?tab=export">
              Pubblicazione e QR
            </a>
          </div>
        </div>
      </div>
    </article>
    """


def _worker_summary_html(r: dict, role: str = "") -> str:
    label_count = int(r.get("label_count") or 0)
    assigned_count = int(r.get("assigned_label_count") or 0)
    pending_count = int(r.get("pending_invite_count") or 0)
    names = (r.get("assigned_studio_names") or "").strip()
    self_count = max(label_count - assigned_count - pending_count, 0)
    states = int(bool(self_count)) + int(bool(assigned_count)) + int(bool(pending_count))

    if label_count > 1 and states > 1:
        tone = "mixed"
        status = "Gestione mista"
        detail = names
    elif pending_count > 0:
        tone = "pending"
        status = "Invito in attesa"
        detail = ""
    elif assigned_count > 0:
        tone = "assigned"
        status = "Studio assegnato"
        detail = names
    else:
        tone = "self"
        status = "Gestisco io"
        detail = ""

    return f"""
    <div class="dashboardManagement dashboardManagement-{tone}" onclick="event.stopPropagation()">
      <div class="dashboardManagementText">
        <span>Gestione</span>
        <b>{_h(status)}</b>
        {f'<small>{_h(detail)}</small>' if detail else ''}
      </div>
    </div>
    """


@router.get("/app/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, q: str = "", work: str = "all"):
    user = require_any_role(request, ("winery", "studio", "admin"))

    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])
    q = (q or "").strip()

    active_context_name = ""
    balances = {"wine": 0, "generic": 0}
    rows = []
    allowed_winery_ids = []
    master_count = 0

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            balances = _balances(cur, uid)

            if role == "admin":
                active = _admin_active_winery_id(cur, uid)

                if not active:
                    actions = (
                        pill(f"wine: {balances['wine']}", "green") + " " +
                        pill(f"generic: {balances['generic']}") + " " +
                        top_actions(
                            ("/admin", "Admin"),
                            ("/app/start", "Menu"),
                            ("/logout", "Logout"),
                        )
                    )

                    body_html = """
                    <section class="dashboardWrap">
                      <div class="dashboardHero">
                        <div>
                          <div class="dashboardEyebrow">Contesto richiesto</div>
                          <div class="h1">Seleziona una cantina</div>
                          <div class="p">
                            Come amministratore devi prima scegliere la cantina su cui lavorare.
                            Da lì potrai vedere lotti, QR code, immagini ed esportazioni.
                          </div>
                        </div>
                      </div>

                      <div class="card" style="margin-top:18px">
                        <div class="h2">Nessun contesto cantina attivo</div>
                        <div class="p">
                          Vai nella console admin e seleziona la cantina operativa.
                        </div>
                        <div style="margin-top:18px">
                          <a class="btn btn-primary" href="/admin">Vai su Admin</a>
                        </div>
                      </div>
                    </section>
                    """

                    return HTMLResponse(page(
                        title="QRFACILE · Dashboard",
                        subtitle="Dashboard",
                        body_html=body_html,
                        actions_html=actions,
                        role=role,
                        user_email=user.get("email", ""),
                        credits=balances,
                    ))

                allowed_winery_ids = [active]
                active_context_name = _admin_active_winery_name(cur, active)

            elif role == "studio":
                cur.execute(
                    """
                    SELECT winery_id
                    FROM studio_clients
                    WHERE studio_user_id=%s
                      AND can_view=TRUE
                    """,
                    (uid,),
                )
                allowed_winery_ids = [int(x["winery_id"]) for x in (cur.fetchall() or [])]

            else:
                cur.execute(
                    "SELECT id FROM wineries WHERE owner_user_id=%s",
                    (uid,),
                )
                allowed_winery_ids = [int(x["id"]) for x in (cur.fetchall() or [])]

            if not allowed_winery_ids:
                if role == "studio":
                    actions = (
                        pill(f"wine: {balances['wine']}", "green") + " " +
                        pill(f"generic: {balances['generic']}") + " " +
                        top_actions(
                            ("/app/start", "Menu"),
                            ("/studio", "Area Studio"),
                            ("/app/billing", "Crediti"),
                            ("/logout", "Logout"),
                        )
                    )

                    body_html = """
                    <section class="dashboardWrap">
                      <div class="dashboardHero">
                        <div>
                          <div class="dashboardEyebrow">Studio grafico</div>
                          <div class="h1">Inizia collegando una cantina</div>
                          <div class="p">
                            Questo account Studio non ha ancora cantine collegate.
                            Vai nell’Area Studio, crea un invito e invialo alla cantina.
                            Quando la cantina si registra dal link, verrà collegata automaticamente al tuo studio.
                          </div>
                        </div>
                      </div>

                      <div class="card" style="margin-top:18px">
                        <div class="h2">Cosa puoi fare adesso</div>
                        <div class="p" style="margin-top:8px">
                          Da Area Studio puoi creare inviti, vedere le cantine collegate e accedere al lavoro operativo.
                        </div>

                        <div class="row" style="margin-top:18px;gap:10px;flex-wrap:wrap">
                          <a class="btn btn-primary" href="/studio">Vai ad Area Studio</a>
                          <a class="btn" href="/app/billing">Crediti e piani</a>
                          <a class="btn" href="/studio/settings">Impostazioni Studio</a>
                          <a class="btn" href="/app/start">Torna al menu</a>
                        </div>
                      </div>

                      <div class="card" style="margin-top:14px">
                        <div class="h2">Come funziona l’invito</div>
                        <div class="p" style="margin-top:8px;line-height:1.6">
                          1. Crei un invito per la cantina.<br>
                          2. La cantina apre il link e completa la registrazione.<br>
                          3. QRFACILE crea automaticamente il collegamento tra Studio e Cantina.<br>
                          4. Da quel momento potrai lavorare sui QR e sulle etichette autorizzate.
                        </div>
                      </div>
                    </section>
                    """

                    return HTMLResponse(page(
                        title="QRFACILE · Dashboard Studio",
                        subtitle="Dashboard Studio",
                        body_html=body_html,
                        actions_html=actions,
                        role=role,
                        user_email=user.get("email", ""),
                        credits=balances,
                    ))

                actions = (
                    pill(f"wine: {balances['wine']}", "green") + " " +
                    pill(f"generic: {balances['generic']}") + " " +
                    top_actions(
                        ("/app/start", "Menu"),
                        ("/app/new-wine", "Nuovo lotto"),
                        ("/logout", "Logout"),
                    )
                )

                body_html = """
                <section class="dashboardWrap">
                  <div class="dashboardHero">
                    <div>
                      <div class="dashboardEyebrow">Dashboard</div>
                      <div class="h1">Nessuna cantina disponibile</div>
                      <div class="p">
                        Non risultano cantine collegate a questo account.
                      </div>
                    </div>
                  </div>
                </section>
                """

                return HTMLResponse(page(
                    title="QRFACILE · Dashboard",
                    subtitle="Dashboard",
                    body_html=body_html,
                    actions_html=actions,
                    role=role,
                    user_email=user.get("email", ""),
                    credits=balances,
                ))

            where = "qw.winery_id = ANY(%s)"
            params = [allowed_winery_ids]
            work = (work or "all").strip().lower()
            if work not in ("all", "self", "assigned", "pending"):
                work = "all"

            cur.execute(
                """
                SELECT COUNT(*)::int AS n
                FROM wines_master
                WHERE winery_id = ANY(%s)
                """,
                (allowed_winery_ids,),
            )
            master_count = int((cur.fetchone() or {}).get("n") or 0)

            if q:
                where += """
                AND (
                  lower(qw.wine_name) LIKE %s
                  OR lower(COALESCE(qw.lot,'')) LIKE %s
                  OR lower(COALESCE(qi.slug,'')) LIKE %s
                )
                """
                like = f"%{q.lower()}%"
                params.extend([like, like, like])

            invite_cols = _columns(cur, "studio_invites")
            has_source_wine = "source_wine_id" in invite_cols
            has_source_label = "source_label_id" in invite_cols

            pending_select = "0::int AS pending_invite_count"
            pending_join = ""
            pending_exists = "FALSE"
            if has_source_wine or has_source_label:
                pending_parts = []
                if has_source_wine:
                    pending_parts.append("si.source_wine_id = qw.id")
                if has_source_label:
                    pending_parts.append("si.source_label_id IN (SELECT wl_p.id FROM wine_labels wl_p WHERE wl_p.wine_id = qw.id)")
                pending_condition = " OR ".join(pending_parts)
                pending_select = "COALESCE(pinv.pending_invite_count, 0) AS pending_invite_count"
                pending_join = f"""
                LEFT JOIN LATERAL (
                  SELECT COUNT(*)::int AS pending_invite_count
                  FROM studio_invites si
                  WHERE si.winery_id = qw.winery_id
                    AND si.used_at IS NULL
                    AND (si.expires_at IS NULL OR si.expires_at >= EXTRACT(EPOCH FROM now())::bigint)
                    AND ({pending_condition})
                ) pinv ON TRUE
                """
                pending_exists = f"""
                EXISTS (
                  SELECT 1
                  FROM studio_invites si
                  WHERE si.winery_id = qw.winery_id
                    AND si.used_at IS NULL
                    AND (si.expires_at IS NULL OR si.expires_at >= EXTRACT(EPOCH FROM now())::bigint)
                    AND ({pending_condition})
                )
                """

            assigned_exists = """
            EXISTS (
              SELECT 1
              FROM wine_labels wl_a
              JOIN label_collaborators lc_a ON lc_a.wine_label_id = wl_a.id
              WHERE wl_a.wine_id = qw.id
                AND lc_a.active = TRUE
                AND lc_a.can_view = TRUE
            )
            """

            if work == "assigned":
                where += f" AND {assigned_exists}"
            elif work == "pending":
                where += f" AND {pending_exists}"
            elif work == "self":
                where += f" AND NOT {assigned_exists} AND NOT {pending_exists}"

            cur.execute(
                f"""
                SELECT
                  qw.id AS wine_id,
                  qw.winery_id,
                  qw.wine_name,
                  qw.vintage,
                  qw.lot,
                  qw.contains_sulfites,
                  qw.contains_egg,
                  qw.contains_milk,
                  qi.slug,
                  qi.status,
                  w.name AS winery_name,
                  wa_front.img_thumb AS front_thumb,
                  wa_back.img_thumb AS back_thumb,
                  COALESCE(ing.ingredient_count, 0) AS ingredient_count,
                  COALESCE(allg.allergen_count, 0) AS allergen_count,
                  COALESCE(rec.recycle_count, 0) AS recycle_count,
                  COALESCE(lbl.label_count, 0) AS label_count,
                  lbl.first_label_id,
                  COALESCE(lca.assigned_label_count, 0) AS assigned_label_count,
                  COALESCE(lca.assigned_studio_names, '') AS assigned_studio_names,
                  {pending_select},
                  COALESCE(wm.extra_ingredients, '') AS extra_ingredients,
                  CASE
                    WHEN wn.energy_kj IS NOT NULL AND wn.energy_kcal IS NOT NULL
                    THEN TRUE
                    ELSE FALSE
                  END AS nutrition_ok
                FROM qr_wines qw
                JOIN qr_items qi ON qi.id = qw.qr_item_id
                JOIN wineries w ON w.id = qw.winery_id

                LEFT JOIN wine_assets wa_front
                  ON wa_front.wine_id = qw.id
                 AND wa_front.kind='front'

                LEFT JOIN wine_assets wa_back
                  ON wa_back.wine_id = qw.id
                 AND wa_back.kind='back'

                LEFT JOIN (
                  SELECT wine_id, COUNT(*)::int AS ingredient_count
                  FROM wine_ingredients
                  GROUP BY wine_id
                ) ing ON ing.wine_id = qw.id

                LEFT JOIN (
                  SELECT wine_id, COUNT(*)::int AS allergen_count
                  FROM wine_allergens
                  GROUP BY wine_id
                ) allg ON allg.wine_id = qw.id

                LEFT JOIN (
                  SELECT wine_id, COUNT(*)::int AS recycle_count
                  FROM wine_recycle_items
                  WHERE COALESCE(BTRIM(product), '') <> ''
                     OR COALESCE(BTRIM(code), '') NOT IN ('', '-')
                     OR COALESCE(BTRIM(extra_code), '') <> ''
                     OR COALESCE(BTRIM(note), '') <> ''
                  GROUP BY wine_id
                ) rec ON rec.wine_id = qw.id

                LEFT JOIN (
                  SELECT wine_id, COUNT(*)::int AS label_count, MIN(id)::int AS first_label_id
                  FROM wine_labels
                  GROUP BY wine_id
                ) lbl ON lbl.wine_id = qw.id

                LEFT JOIN (
                  SELECT
                    wl.wine_id,
                    COUNT(DISTINCT wl.id)::int AS assigned_label_count,
                    STRING_AGG(DISTINCT COALESCE(NULLIF(s.company_name, ''), u.email), ', ') AS assigned_studio_names
                  FROM wine_labels wl
                  JOIN label_collaborators lc ON lc.wine_label_id = wl.id
                  JOIN users u ON u.id = lc.collaborator_user_id
                  LEFT JOIN studios s ON s.user_id = u.id
                  WHERE lc.active=TRUE AND lc.can_view=TRUE
                  GROUP BY wl.wine_id
                ) lca ON lca.wine_id = qw.id

                {pending_join}

                LEFT JOIN wine_nutrition wn
                  ON wn.wine_id = qw.id

                LEFT JOIN wine_meta wm
                  ON wm.wine_id = qw.id

                WHERE {where}
                ORDER BY qw.id DESC
                LIMIT 200
                """,
                tuple(params),
            )

            rows = cur.fetchall() or []

            if role in ("winery", "admin"):
                wine_ids = [int(r["wine_id"]) for r in rows]
                winery_ids = sorted({int(r["winery_id"]) for r in rows if r.get("winery_id")})
                labels_by_wine, studios_by_winery = _load_inline_management(cur, wine_ids, winery_ids)
            else:
                labels_by_wine, studios_by_winery = {}, {}

    actions = (
        pill(f"wine: {balances['wine']}", "green") + " " +
        pill(f"generic: {balances['generic']}") + " " +
        top_actions(
            ("/app/start", "Menu"),
            ("/app/new-wine-master", "Nuova etichetta"),
            ("/app/new-wine", "Nuovo lotto"),
            ("/app/new-external", "QR Link"),
            ("/app/billing", "Crediti"),
            ("/logout", "Logout"),
        )
    )

    new_lot_btn = '<a class="btn" href="/app/new-wine">Nuovo lotto</a>'
    toolbar_new_lot_btn = '<a class="btn btn-primary" href="/app/new-wine">Nuovo lotto</a>'
    no_master_notice = ""
    if master_count <= 0:
        new_lot_btn = '<span class="btn" aria-disabled="true" style="opacity:.58;cursor:not-allowed">Nuovo lotto</span>'
        toolbar_new_lot_btn = '<span class="btn btn-primary" aria-disabled="true" style="opacity:.58;cursor:not-allowed">Nuovo lotto</span>'
        no_master_notice = """
        <div class="note" style="margin-top:12px">
          Crea prima una <b>etichetta/prodotto</b>: i lotti si collegano sempre a una etichetta esistente.
        </div>
        """

    qr_definitive_notice = """
    <div class="note" style="margin-top:14px">
      Il QR generato è già quello definitivo e può essere inviato immediatamente al tipografo.
      La pagina pubblica non sarà visibile finché non saranno completati tutti i dati obbligatori
      e la pubblicazione non sarà confermata.
    </div>
    """

    cards_html = "\n".join([_wine_card(r, role, labels_by_wine, studios_by_winery) for r in rows])

    if not cards_html:
        empty_message = "Nessun lotto trovato"
        empty_detail = "Crea il primo lotto vino oppure modifica la ricerca."

        if q:
            empty_message = "Nessun risultato per la ricerca"
            empty_detail = "Prova con nome vino, lotto o slug diverso."

        cards_html = f"""
        <div class="dashboardEmpty card">
          <div class="dashboardEmptyIcon">🍷</div>
          <div>
            <div class="h2">{empty_message}</div>
            <div class="p">{empty_detail}</div>
            <div style="margin-top:18px;display:flex;gap:12px;flex-wrap:wrap">
              <a class="btn btn-primary" href="/app/new-wine-master">Crea nuova etichetta</a>
              {toolbar_new_lot_btn}
              <a class="btn" href="/app/dashboard">Azzera ricerca</a>
            </div>
          </div>
        </div>
        """

    context_html = ""
    if active_context_name:
        context_html = f"""
        <div class="dashboardContextBox">
          <div>Contesto admin</div>
          <b>{esc(active_context_name)}</b>
        </div>
        """

    counts = _dashboard_counts(rows)
    onboarding_html = _onboarding_html(rows, role)

    body = f"""
    <section class="dashboardWrap">
      <div class="dashboardHero">
        <div>
          <div class="dashboardEyebrow">Dashboard Wine</div>

          <div class="dashboardHeroTop">
            <div>
              <div class="h1">Etichette e lotti</div>
              <div class="p">
                Crea prima l’etichetta/prodotto, poi aggiungi i lotti collegati, verifica i dati obbligatori e pubblica solo quando tutto è pronto.
              </div>
              <div class="dashboardHeroActions">
                <a class="btn btn-primary" href="/app/new-wine-master">Nuova etichetta</a>
                {new_lot_btn}
                <a class="btn" href="/app/labels/search">Ricerca avanzata</a>
              </div>
              {no_master_notice}
              {qr_definitive_notice}
            </div>

            {context_html}
          </div>
        </div>

        <div class="dashboardHeroStats">
          <div class="dashboardStat">
            <span>Lotti completi</span>
            <b>{counts['complete']}</b>
          </div>

          <div class="dashboardStat">
            <span>Incompleti</span>
            <b>{counts['incomplete']}</b>
          </div>

          <div class="dashboardStat">
            <span>Pubblicati</span>
            <b>{counts['published']}</b>
          </div>
        </div>
      </div>

      {onboarding_html}

      <div class="dashboardToolbar card">
        <form method="get" class="dashboardSearchForm">
          <div>
            <label style="margin-top:0">Cerca lotto, vino o slug</label>
            <input class="input" name="q" value="{_h(q)}" placeholder="Es. Falanghina, lotto L25, slug...">
          </div>

          <div>
            <label style="margin-top:0">Chi lavora</label>
            <select name="work">
              <option value="all" {'selected' if work == 'all' else ''}>Tutte</option>
              <option value="self" {'selected' if work == 'self' else ''}>Gestisco io</option>
              <option value="assigned" {'selected' if work == 'assigned' else ''}>Studio assegnato</option>
              <option value="pending" {'selected' if work == 'pending' else ''}>Invito in attesa</option>
            </select>
          </div>

          <div class="dashboardToolbarActions">
            <button class="btn btn-primary" type="submit">Cerca</button>
            <a class="btn" href="/app/dashboard">Azzera</a>
            {toolbar_new_lot_btn}
          </div>
        </form>
      </div>

      <div class="dashboardList">
        {cards_html}
      </div>

      <style>
        .dashboardWrap {{
          max-width:1180px;
          margin:0 auto;
        }}

        .dashboardHero {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:28px;
          overflow:hidden;
          box-shadow:0 24px 80px rgba(2,8,23,.08);
          background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(248,252,250,.94));
          padding:30px;
          display:grid;
          grid-template-columns:1.4fr .8fr;
          gap:24px;
          align-items:end;
        }}

        .dashboardEyebrow {{
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

        .dashboardHeroTop {{
          display:flex;
          justify-content:space-between;
          gap:18px;
          align-items:flex-start;
          flex-wrap:wrap;
        }}

        .dashboardHeroActions {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:18px;
        }}

        .dashboardContextBox {{
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.72);
          border-radius:20px;
          padding:14px 16px;
          min-width:190px;
        }}

        .dashboardContextBox div {{
          color:#64748b;
          font-size:12px;
          font-weight:900;
          text-transform:uppercase;
          letter-spacing:.07em;
        }}

        .dashboardContextBox b {{
          display:block;
          margin-top:5px;
          font-size:15px;
        }}

        .dashboardHeroStats {{
          display:grid;
          grid-template-columns:repeat(3,minmax(0,1fr));
          gap:12px;
        }}

        .dashboardStat {{
          border:1px solid rgba(2,8,23,.07);
          background:rgba(255,255,255,.72);
          border-radius:22px;
          padding:16px;
        }}

        .dashboardStat span {{
          display:block;
          font-size:12px;
          color:#64748b;
          font-weight:900;
        }}

        .dashboardStat b {{
          display:block;
          margin-top:6px;
          font-size:30px;
          line-height:1;
          font-weight:950;
        }}

        .dashboardOnboarding {{
          margin-top:18px;
          padding:20px;
        }}

        .dashboardOnboardingHead {{
          display:flex;
          justify-content:space-between;
          gap:20px;
          align-items:flex-start;
        }}

        .dashboardSectionKicker {{
          color:#0f766e;
          font-size:12px;
          font-weight:950;
          letter-spacing:.08em;
          text-transform:uppercase;
          margin-bottom:6px;
        }}

        .dashboardProgressBox {{
          min-width:230px;
          border:1px solid rgba(2,8,23,.08);
          background:rgba(248,250,252,.78);
          border-radius:18px;
          padding:14px;
        }}

        .dashboardProgressLabel {{
          display:flex;
          justify-content:space-between;
          gap:12px;
          align-items:center;
        }}

        .dashboardProgressLabel span {{
          color:#64748b;
          font-size:12px;
          font-weight:900;
        }}

        .dashboardProgressLabel b {{
          font-size:20px;
          font-weight:950;
        }}

        .dashboardProgressTrack {{
          height:9px;
          margin-top:10px;
          border-radius:999px;
          overflow:hidden;
          background:#e2e8f0;
        }}

        .dashboardProgressTrack span {{
          display:block;
          height:100%;
          border-radius:999px;
          background:#0f766e;
        }}

        .dashboardGlobalState {{
          display:grid;
          grid-template-columns:repeat(3,minmax(0,1fr));
          gap:10px;
          margin-top:18px;
        }}

        .dashboardGlobalState div {{
          border:1px solid rgba(2,8,23,.07);
          border-radius:18px;
          background:rgba(255,255,255,.72);
          padding:13px;
        }}

        .dashboardGlobalState span {{
          display:block;
          color:#64748b;
          font-size:12px;
          font-weight:900;
        }}

        .dashboardGlobalState b {{
          display:block;
          margin-top:4px;
          font-size:24px;
          font-weight:950;
        }}

        .dashboardOnboardingGrid {{
          display:grid;
          grid-template-columns:minmax(0,1fr) 300px;
          gap:16px;
          margin-top:18px;
        }}

        .dashboardChecklist {{
          display:grid;
          grid-template-columns:repeat(4,minmax(0,1fr));
          gap:10px;
        }}

        .dashboardOnboardingCheck {{
          display:flex;
          gap:10px;
          align-items:flex-start;
          border:1px solid rgba(2,8,23,.07);
          border-radius:18px;
          background:rgba(255,255,255,.72);
          padding:12px;
        }}

        .dashboardOnboardingCheck span {{
          width:28px;
          height:28px;
          border-radius:999px;
          display:inline-flex;
          align-items:center;
          justify-content:center;
          flex:0 0 auto;
          font-size:12px;
          font-weight:950;
          background:#f59e0b;
          color:#fff;
        }}

        .dashboardOnboardingCheck.ok span {{
          background:#10b981;
        }}

        .dashboardOnboardingCheck b {{
          display:block;
          font-size:13px;
          font-weight:950;
        }}

        .dashboardOnboardingCheck small {{
          display:block;
          margin-top:3px;
          color:#64748b;
          font-size:11px;
          font-weight:800;
        }}

        .dashboardNextStep {{
          border:1px solid rgba(15,118,110,.16);
          background:rgba(236,253,245,.62);
          border-radius:20px;
          padding:16px;
        }}

        .dashboardNextStep span {{
          color:#0f766e;
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.07em;
        }}

        .dashboardNextStep b {{
          display:block;
          margin-top:7px;
          font-size:22px;
          font-weight:950;
          letter-spacing:-.25px;
        }}

        .dashboardNextStep small {{
          display:block;
          margin-top:7px;
          color:#475569;
          font-size:13px;
          font-weight:750;
          line-height:1.45;
        }}

        .dashboardNextActions {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:16px;
        }}

        .dashboardInlineForm {{
          display:inline;
          margin:0;
        }}

        .dashboardToolbar {{
          margin-top:18px;
        }}

        .dashboardSearchForm {{
          display:grid;
          grid-template-columns:minmax(0,1fr) 220px auto;
          gap:16px;
          align-items:end;
        }}

        .dashboardToolbarActions {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          justify-content:flex-end;
        }}

        .dashboardList {{
          display:grid;
          gap:16px;
          margin-top:18px;
        }}

        .dashboardWineCard {{
          cursor:pointer;
          padding:0;
          overflow:hidden;
        }}

        .dashboardWineCard:hover {{
          transform:translateY(-2px);
          border-color:rgba(20,184,166,.22);
        }}

        .dashboardWineMain {{
          display:grid;
          grid-template-columns:170px minmax(0,1fr);
          gap:18px;
          padding:18px;
        }}

        .dashboardThumbs {{
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:10px;
        }}

        .dashboardThumbBox {{
          position:relative;
          border:1px solid rgba(2,8,23,.08);
          border-radius:18px;
          overflow:hidden;
          min-height:128px;
          background:
            radial-gradient(circle at 20% 10%, rgba(191,245,230,.45), transparent 50%),
            rgba(255,255,255,.78);
        }}

        .dashboardThumbBox img {{
          width:100%;
          height:128px;
          object-fit:cover;
          display:block;
        }}

        .dashboardThumbBox span {{
          position:absolute;
          left:8px;
          bottom:8px;
          padding:4px 8px;
          border-radius:999px;
          background:rgba(255,255,255,.84);
          font-size:11px;
          font-weight:900;
          color:#334155;
          border:1px solid rgba(2,8,23,.06);
        }}

        .dashboardWineContent {{
          min-width:0;
          display:flex;
          flex-direction:column;
          justify-content:space-between;
          gap:18px;
        }}

        .dashboardWineTop {{
          display:flex;
          justify-content:space-between;
          gap:18px;
          align-items:flex-start;
        }}

        .dashboardWineInfo {{
          min-width:0;
          flex:1;
        }}

        .dashboardWineRight {{
          min-width:230px;
          max-width:310px;
          display:grid;
          gap:12px;
          justify-items:end;
        }}

        .dashboardWineTitleRow {{
          display:flex;
          gap:10px;
          align-items:center;
          flex-wrap:wrap;
        }}

        .dashboardWineTitleRow h2 {{
          margin:0;
          font-size:24px;
          line-height:1.12;
          letter-spacing:-.45px;
        }}

        .dashboardWineryName {{
          margin-top:8px;
          color:#64748b;
          font-weight:800;
        }}

        .dashboardMeta {{
          display:flex;
          gap:8px;
          flex-wrap:wrap;
          margin-top:12px;
        }}

        .dashboardMetaPill {{
          display:inline-flex;
          align-items:center;
          padding:7px 10px;
          border-radius:999px;
          background:rgba(255,255,255,.72);
          border:1px solid rgba(2,8,23,.07);
          color:#475569;
          font-size:12px;
          font-weight:900;
        }}

        .dashboardChecks {{
          display:flex;
          gap:8px;
          flex-wrap:wrap;
          margin-top:14px;
        }}

        .dashboardMiniCheck {{
          display:inline-flex;
          align-items:center;
          gap:6px;
          padding:7px 10px;
          border-radius:999px;
          border:1px solid rgba(2,8,23,.07);
          background:rgba(255,255,255,.70);
          font-size:11px;
          font-weight:950;
          color:#475569;
        }}

        .dashboardMiniCheck b {{
          width:17px;
          height:17px;
          border-radius:999px;
          display:inline-flex;
          align-items:center;
          justify-content:center;
          font-size:11px;
          line-height:1;
        }}

        .dashboardMiniCheck.ok {{
          color:#0f766e;
          background:rgba(236,253,245,.78);
          border-color:rgba(20,184,166,.15);
        }}

        .dashboardMiniCheck.ok b {{
          background:#10b981;
          color:#fff;
        }}

        .dashboardMiniCheck.ko {{
          color:#92400e;
          background:rgba(255,251,235,.78);
          border-color:rgba(245,158,11,.18);
        }}

        .dashboardMiniCheck.ko b {{
          background:#f59e0b;
          color:#fff;
        }}

        .dashboardManagement {{
          margin-top:12px;
          display:flex;
          align-items:center;
          justify-content:space-between;
          gap:10px;
          max-width:520px;
          min-height:40px;
        }}

        .dashboardManagementText {{
          min-width:0;
          display:grid;
          gap:2px;
        }}

        .dashboardManagementText span {{
          color:#64748b;
          font-size:11px;
          font-weight:900;
          text-transform:uppercase;
          letter-spacing:.06em;
        }}

        .dashboardManagementText b {{
          display:inline-flex;
          align-items:center;
          width:max-content;
          max-width:220px;
          padding:5px 9px;
          border-radius:999px;
          background:rgba(248,250,252,.92);
          color:#0f172a;
          font-weight:950;
          white-space:nowrap;
          overflow:hidden;
          text-overflow:ellipsis;
        }}

        .dashboardManagementText small {{
          color:#334155;
          font-weight:850;
          line-height:1.25;
          display:-webkit-box;
          -webkit-line-clamp:2;
          -webkit-box-orient:vertical;
          overflow:hidden;
        }}

        .dashboardManagement-assigned b {{
          background:rgba(236,253,245,.88);
          color:#0f766e;
        }}

        .dashboardManagement-pending b {{
          background:rgba(255,251,235,.92);
          color:#92400e;
        }}

        .dashboardManagement-mixed b {{
          background:rgba(239,246,255,.92);
          color:#1d4ed8;
        }}

        .dashboardManagementAction {{
          display:inline-flex;
          align-items:center;
          flex:0 0 auto;
          padding:6px 10px;
          border-radius:999px;
          background:white;
          color:#0f172a;
          font-weight:900;
          white-space:nowrap;
          box-shadow:inset 0 0 0 1px rgba(2,8,23,.08);
        }}

        .dashboardManagementPickers {{
          margin-top:10px;
          display:grid;
          gap:8px;
        }}

        .dashboardManagementPicker {{
          display:grid;
          grid-template-columns:minmax(92px, 140px) minmax(160px, 1fr) auto;
          gap:8px;
          align-items:center;
          max-width:520px;
        }}

        .dashboardManagementPicker span {{
          font-size:12px;
          font-weight:900;
          color:#475569;
        }}

        .dashboardManagementPicker select {{
          min-width:0;
        }}

        .dashboardCompliance {{
          width:100%;
          display:flex;
          align-items:flex-start;
          gap:10px;
          padding:12px 13px;
          border-radius:18px;
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.72);
          text-align:left;
        }}

        .dashboardComplianceDot {{
          width:12px;
          height:12px;
          border-radius:999px;
          margin-top:4px;
          flex:0 0 auto;
        }}

        .dashboardCompliance b {{
          display:block;
          font-size:13px;
          font-weight:950;
          line-height:1.2;
        }}

        .dashboardCompliance small {{
          display:block;
          margin-top:3px;
          color:#64748b;
          font-size:11px;
          font-weight:800;
          line-height:1.35;
        }}

        .dashboardComplianceGreen {{
          background:rgba(236,253,245,.78);
          border-color:rgba(20,184,166,.17);
        }}

        .dashboardComplianceGreen .dashboardComplianceDot {{
          background:#10b981;
          box-shadow:0 0 0 4px rgba(16,185,129,.13);
        }}

        .dashboardComplianceYellow {{
          background:rgba(255,251,235,.84);
          border-color:rgba(245,158,11,.18);
        }}

        .dashboardComplianceYellow .dashboardComplianceDot {{
          background:#f59e0b;
          box-shadow:0 0 0 4px rgba(245,158,11,.13);
        }}

        .dashboardComplianceRed {{
          background:rgba(254,242,242,.84);
          border-color:rgba(239,68,68,.18);
        }}

        .dashboardComplianceRed .dashboardComplianceDot {{
          background:#ef4444;
          box-shadow:0 0 0 4px rgba(239,68,68,.12);
        }}

        .dashboardWineActions {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          justify-content:flex-end;
        }}

        .dashboardWineFooter {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          padding-top:14px;
          border-top:1px solid rgba(2,8,23,.07);
        }}

        .dashboardInlineLink {{
          display:inline-flex;
          padding:8px 11px;
          border-radius:999px;
          background:rgba(236,253,245,.70);
          border:1px solid rgba(20,184,166,.12);
          font-size:12px;
          font-weight:900;
          color:#0f766e;
        }}

        .dashboardEmpty {{
          display:flex;
          gap:16px;
          align-items:flex-start;
        }}

        .dashboardEmptyIcon {{
          width:58px;
          height:58px;
          border-radius:20px;
          display:flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.85),rgba(207,232,255,.85));
          font-size:28px;
          flex:0 0 auto;
        }}

        @media(max-width:1050px) {{
          .dashboardHero {{
            grid-template-columns:1fr;
          }}

          .dashboardSearchForm,
          .dashboardOnboardingGrid {{
            grid-template-columns:1fr;
          }}

          .dashboardOnboardingHead {{
            flex-direction:column;
          }}

          .dashboardProgressBox {{
            width:100%;
          }}

          .dashboardChecklist {{
            grid-template-columns:repeat(2,minmax(0,1fr));
          }}

          .dashboardToolbarActions {{
            justify-content:flex-start;
          }}
        }}

        @media(max-width:920px) {{
          .dashboardWineTop {{
            flex-direction:column;
          }}

          .dashboardWineRight {{
            width:100%;
            max-width:none;
            justify-items:start;
          }}

          .dashboardWineActions {{
            justify-content:flex-start;
          }}

          .dashboardManagementPicker {{
            grid-template-columns:1fr;
          }}
        }}

        @media(max-width:820px) {{
          .dashboardHeroStats,
          .dashboardGlobalState {{
            grid-template-columns:1fr;
          }}

          .dashboardWineMain {{
            grid-template-columns:1fr;
          }}
        }}

        @media(max-width:560px) {{
          .dashboardHero {{
            padding:22px;
          }}

          .dashboardThumbs {{
            grid-template-columns:1fr 1fr;
          }}

          .dashboardChecklist {{
            grid-template-columns:1fr;
          }}

          .dashboardWineActions .btn,
          .dashboardToolbarActions .btn,
          .dashboardHeroActions .btn,
          .dashboardNextActions .btn {{
            width:100%;
          }}
        }}
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Dashboard",
        subtitle="Dashboard",
        body_html=body,
        actions_html=actions,
        role=role,
        user_email=user.get("email", ""),
        credits=balances,
    ))
