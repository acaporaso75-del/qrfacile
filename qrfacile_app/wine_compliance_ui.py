import time
from typing import Optional

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from psycopg.rows import dict_row

from qrfacile_app.db import pg
from qrfacile_app.auth_core import require_any_role
from qrfacile_app.ui_shell import page, top_actions, pill, esc
from qrfacile_app.guided_flow import render_guided_stepper

router = APIRouter()


def now() -> int:
    return int(time.time())


COMPONENTS = [
    ("bottle", "Bottiglia"),
    ("closure", "Tappo"),
    ("capsule", "Capsula"),
    ("label", "Etichetta"),
    ("box", "Scatola"),
    ("other", "Altro"),
]


def _wine(cur, wine_id: int) -> dict:
    cur.execute(
        """
        SELECT qw.id AS wine_id,
               qw.winery_id,
               qw.wine_name,
               qw.vintage,
               qw.lot,
               qi.slug,
               w.name AS winery_name
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


def _redirect(wine_id: int, msg: str = ""):
    if msg:
        return RedirectResponse(
            f"/app/wine/{int(wine_id)}/compliance?msg={msg.replace(' ', '%20')}",
            status_code=303,
        )

    return RedirectResponse(f"/app/wine/{int(wine_id)}/compliance", status_code=303)


def _upsert_meta(cur, wine_id: int, extra_ingredients: str, story_text: str, public_theme: str):
    cur.execute(
        """
        INSERT INTO wine_meta (wine_id, extra_ingredients, story_text, public_theme, updated_at)
        VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT (wine_id) DO UPDATE SET
          extra_ingredients=EXCLUDED.extra_ingredients,
          story_text=EXCLUDED.story_text,
          public_theme=EXCLUDED.public_theme,
          updated_at=EXCLUDED.updated_at
        """,
        (
            int(wine_id),
            (extra_ingredients or "").strip(),
            (story_text or "").strip(),
            (public_theme or "minimal").strip() or "minimal",
            now(),
        ),
    )


def _upsert_nutrition(
    cur,
    wine_id: int,
    energy_kj: Optional[int],
    energy_kcal: Optional[int],
    fat: str,
    saturates: str,
    carbs: str,
    sugars: str,
    protein: str,
    salt: str,
):
    def clean_num_text(v: str) -> str:
        """
        La tabella wine_nutrition non accetta NULL su alcuni valori.
        Se il campo è vuoto, salviamo 0.
        Manteniamo stringa per compatibilità con colonne numeric/text già presenti.
        """
        v = (v or "").strip().replace(",", ".")
        return v if v else "0"

    cur.execute(
        """
        INSERT INTO wine_nutrition (
          wine_id, energy_kj, energy_kcal, fat, saturates, carbs, sugars, protein, salt, updated_at
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (wine_id) DO UPDATE SET
          energy_kj=EXCLUDED.energy_kj,
          energy_kcal=EXCLUDED.energy_kcal,
          fat=EXCLUDED.fat,
          saturates=EXCLUDED.saturates,
          carbs=EXCLUDED.carbs,
          sugars=EXCLUDED.sugars,
          protein=EXCLUDED.protein,
          salt=EXCLUDED.salt,
          updated_at=EXCLUDED.updated_at
        """,
        (
            int(wine_id),
            energy_kj,
            energy_kcal,
            clean_num_text(fat),
            clean_num_text(saturates),
            clean_num_text(carbs),
            clean_num_text(sugars),
            clean_num_text(protein),
            clean_num_text(salt),
            now(),
        ),
    )


def _upsert_recycle_item(
    cur,
    wine_id: int,
    component: str,
    product: str,
    code: str,
    extra_code: str,
    note: str,
):
    code_clean = (code or "").strip()
    if not code_clean:
        code_clean = "-"

    cur.execute(
        """
        INSERT INTO wine_recycle_items (wine_id, component, code, note, updated_at, product, extra_code)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (wine_id, component) DO UPDATE SET
          code=EXCLUDED.code,
          note=EXCLUDED.note,
          updated_at=EXCLUDED.updated_at,
          product=EXCLUDED.product,
          extra_code=EXCLUDED.extra_code
        """,
        (
            int(wine_id),
            component,
            code_clean,
            (note or "").strip() or None,
            now(),
            (product or "").strip() or None,
            (extra_code or "").strip() or None,
        ),
    )


def _load_page_data(wine_id: int) -> dict:
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _wine(cur, int(wine_id))

            cur.execute(
                """
                SELECT energy_kj, energy_kcal, fat, saturates, carbs, sugars, protein, salt
                FROM wine_nutrition
                WHERE wine_id=%s
                LIMIT 1
                """,
                (int(wine_id),),
            )
            nut = cur.fetchone() or {}

            cur.execute(
                """
                SELECT im.name
                FROM wine_ingredients wi
                JOIN ingredients_master im ON im.id = wi.ingredient_id
                WHERE wi.wine_id=%s
                ORDER BY lower(im.name)
                """,
                (int(wine_id),),
            )
            ingredients = [r["name"] for r in (cur.fetchall() or []) if r.get("name")]

            cur.execute(
                """
                SELECT COALESCE(am.name, wa.custom_text) AS name
                FROM wine_allergens wa
                LEFT JOIN allergens_master am ON am.id = wa.allergen_id
                WHERE wa.wine_id=%s
                ORDER BY COALESCE(am.name, wa.custom_text)
                """,
                (int(wine_id),),
            )
            allergens = [r["name"] for r in (cur.fetchall() or []) if r.get("name")]

            cur.execute(
                """
                SELECT component, product, code, extra_code, note
                FROM wine_recycle_items
                WHERE wine_id=%s
                ORDER BY component
                """,
                (int(wine_id),),
            )
            recycle = {r["component"]: r for r in (cur.fetchall() or [])}

            cur.execute(
                """
                SELECT extra_ingredients, story_text, public_theme
                FROM wine_meta
                WHERE wine_id=%s
                LIMIT 1
                """,
                (int(wine_id),),
            )
            meta = cur.fetchone() or {}

    return {
        "wine": w,
        "nutrition": nut,
        "ingredients": ingredients,
        "allergens": allergens,
        "recycle": recycle,
        "meta": meta,
    }


def _val(x) -> str:
    return "" if x is None else str(x)


def _chip_html(items: list[str], empty: str) -> str:
    if not items:
        return f"<span class='complianceMuted'>{esc(empty)}</span>"

    return "".join([f"<span class='complianceChip'>{esc(x)}</span>" for x in items])


def _status_chip(label: str, ok: bool) -> str:
    cls = "ok" if ok else "todo"
    icon = "✓" if ok else "!"
    return f"""
    <span class="complianceStatusChip {cls}">
      <b>{icon}</b>
      {esc(label)}
    </span>
    """


def _summary_html(ingredients: list[str], allergens: list[str], nut: dict, recycle: dict, meta: dict, role: str = '', wine_id: int = 0) -> str:
    extra_ingredients = (meta.get("extra_ingredients") or "").strip()

    ingredient_ok = bool(ingredients) or bool(extra_ingredients)
    allergen_ok = bool(allergens)
    nutrition_ok = nut.get("energy_kj") is not None and nut.get("energy_kcal") is not None
    recycle_ok = bool(recycle)

    checks = [
        ("Ingredienti", ingredient_ok),
        ("Allergeni", allergen_ok),
        ("Energia kJ/kcal", nutrition_ok),
        ("Riciclabilità", recycle_ok),
    ]

    missing = [label for label, ok in checks if not ok]
    done = [label for label, ok in checks if ok]

    if missing:
        title = "Dati obbligatori da completare"
        detail = "Completa i campi mancanti prima di considerare pronta l’etichetta digitale."
        box_cls = "todo"
    else:
        title = "Compliance principale completa"
        detail = "I dati obbligatori principali risultano compilati."
        box_cls = "ok"

    missing_html = "".join(_status_chip(x, False) for x in missing)
    done_html = "".join(_status_chip(x, True) for x in done)

    missing_block = ""
    if missing:
        missing_block = f"""
        <div class="complianceSummaryBlock">
          <div class="complianceSummaryLabel">Mancano</div>
          <div class="complianceSummaryChips">{missing_html}</div>
        </div>
        """

    done_block = ""
    if done:
        done_block = f"""
        <div class="complianceSummaryBlock">
          <div class="complianceSummaryLabel">Completi</div>
          <div class="complianceSummaryChips">{done_html}</div>
        </div>
        """

    request_block = ""
    if missing and (role or "").lower().strip() == "winery" and int(wine_id or 0) > 0:
        request_block = f"""
        <form method="post"
              action="/app/wine/{int(wine_id)}/request-publish-override"
              class="complianceOverrideRequest">
          <div>
            <label>Richiesta sblocco admin</label>
            <input class="input" name="reason"
                   placeholder="Motivo richiesta, es. test stampa, urgenza, dati in verifica...">
          </div>
          <button class="btn" type="submit">Richiedi sblocco admin</button>
        </form>
        """

    return f"""
    <div class="complianceSummaryBox {box_cls}">
      <div class="complianceSummaryHead">
        <div class="complianceSummaryDot"></div>
        <div>
          <div class="complianceSummaryTitle">{esc(title)}</div>
          <div class="complianceSummaryText">{esc(detail)}</div>
        </div>
      </div>
      {missing_block}
      {done_block}
      {request_block}
    </div>
    """


def _recycle_rows(recycle: dict) -> str:
    rows = []

    for key, label in COMPONENTS:
        r = recycle.get(key) or {}

        rows.append(f"""
        <div class="complianceRecycleCard">
          <div class="complianceRecycleHead">
            <div>
              <div class="complianceSmallLabel">Componente</div>
              <div class="h2">{esc(label)}</div>
            </div>
            <span class="pill pill-muted">Codice obbligatorio</span>
          </div>

          <div class="complianceRecycleGrid">
            <div>
              <label>Prodotto / materiale</label>
              <input class="input" name="rec_{key}_product"
                     value="{esc(_val(r.get('product')))}"
                     placeholder="es. vetro verde / sughero / alluminio">
            </div>

            <div>
              <label>Codice</label>
              <input class="input mono" name="rec_{key}_code"
                     value="{esc(_val(r.get('code')))}"
                     placeholder="es. GL71">
            </div>

            <div>
              <label>Codice extra</label>
              <details class="qrfAdvanced"><summary>Opzioni avanzate</summary>
                <label>Codice aggiuntivo eccezionale</label>
                <input class="input mono" name="rec_{key}_extra"
                       value="{esc(_val(r.get('extra_code')))}"
                       placeholder="Solo se documentato dal fornitore">
                <small>Non usare per il normale codice del materiale. Compilare solo quando il fornitore richiede un secondo riferimento documentato.</small>
              </details>
            </div>

            <div>
              <label>Note</label>
              <input class="input" name="rec_{key}_note"
                     value="{esc(_val(r.get('note')))}"
                     placeholder="facoltativo">
            </div>
          </div>
        </div>
        """)

    return "\n".join(rows)


@router.get("/app/wine/{wine_id}/compliance", response_class=HTMLResponse)
def compliance_get(request: Request, wine_id: int, msg: str = ""):
    user = require_any_role(request, ("winery", "studio", "admin"))
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    data = _load_page_data(int(wine_id))
    w = data["wine"]

    require_any_role(
        request,
        ("winery", "studio", "admin"),
        winery_id=int(w["winery_id"]),
        need="view",
    )

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            balances = _balances(cur, uid)

    nut = data["nutrition"]
    ingredients = data["ingredients"]
    allergens = data["allergens"]
    recycle = data["recycle"]
    meta = data["meta"]

    actions = (
        pill(f"wine: {balances.get('wine', 0)}", "green") + " " +
        pill(f"generic: {balances.get('generic', 0)}") + " " +
        top_actions(
            (f"/app/wine/{int(wine_id)}", "Overview"),
            ("/app/dashboard", "Dashboard"),
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

    wine_name = esc(w.get("wine_name") or "")
    winery_name = esc(w.get("winery_name") or "")
    lot = esc(w.get("lot") or "")
    vintage = esc(str(w.get("vintage") or "").strip())

    vintage_html = f"<span>Annata <b>{vintage}</b></span>" if vintage else ""
    lot_html = f"<span>Lotto <b>{lot}</b></span>" if lot else ""

    ingredient_chips = _chip_html(ingredients, "Nessun ingrediente selezionato")
    allergen_chips = _chip_html(allergens, "Nessun allergene selezionato")
    rec_html = _recycle_rows(recycle)

    theme = (meta.get("public_theme") or "minimal").strip() or "minimal"
    summary_html = _summary_html(ingredients, allergens, nut, recycle, meta, role=role, wine_id=int(wine_id))

    body = f"""
    <section class="complianceWrap">
      <div class="complianceHero">
        <div>
          <div class="complianceEyebrow">Compliance vino</div>
          <div class="h1">Dati obbligatori</div>
          <div class="p">
            Compila ingredienti, allergeni, valori nutrizionali, riciclabilità e contenuti pubblici
            per il lotto <b>{wine_name}</b> della cantina <b>{winery_name}</b>.
          </div>

          <div class="complianceMeta">
            {vintage_html}
            {lot_html}
          </div>

          {msg_html}
          {summary_html}
        </div>

        <div class="complianceHeroCard"><div class="complianceHeroCardTitle">Percorso guidato</div><p>Salva ogni sezione e continua fino al controllo finale.</p></div>
      </div>

      {render_guided_stepper(int(wine_id), "ingredients", {"wine"})}

      <div class="complianceTabs">
        <a class="complianceTab" href="/app/wine/{int(wine_id)}">Overview</a>
        <a class="complianceTab" href="/app/wine/{int(wine_id)}/images">Immagini</a>
        <a class="complianceTab active" href="/app/wine/{int(wine_id)}/compliance">Compliance</a>
        <a class="complianceTab" href="/app/wine/{int(wine_id)}/export">Export</a>
      </div>

      <div class="complianceFlow" style="display:none">
        <a href="/app/wine/{int(wine_id)}/images">
          <span>1</span>
          <b>Immagini</b>
          <small>Carica fronte e retro</small>
        </a>

        <a class="active" href="/app/wine/{int(wine_id)}/compliance">
          <span>2</span>
          <b>Compliance</b>
          <small>Compila i dati obbligatori</small>
        </a>

        <a href="/app/wine/{int(wine_id)}/export">
          <span>3</span>
          <b>Export</b>
          <small>Scarica QR per stampa</small>
        </a>
      </div>

      <div class="complianceGrid2" id="ingredienti">
        <div class="card compliancePanel">
          <div class="compliancePanelHead">
            <div>
              <div class="complianceSmallLabel">Ingredienti</div>
              <div class="h2">Ingredienti selezionati</div>
            </div>
            <span class="complianceIcon">🍇</span>
          </div>

          <div class="complianceChips">
            {ingredient_chips}
          </div>

          <form method="post"
                action="/app/wine/{int(wine_id)}/compliance/add-ingredient"
                class="complianceInlineForm">
            <div>
              <label>Aggiungi ingrediente</label>
              <input class="input" name="name"
                     placeholder="es. uva, mosto, anidride solforosa..."
                     required>
            </div>

            <button class="btn" type="submit">Aggiungi ingrediente</button>
          </form>

          <div class="note" style="margin-top:14px">
            Se l’ingrediente non esiste nel database, viene aggiunto come testo libero.
          </div>
        </div>

        <div class="card compliancePanel">
          <div class="compliancePanelHead">
            <div>
              <div class="complianceSmallLabel">Allergeni</div>
              <div class="h2">Allergeni dichiarati</div>
            </div>
            <span class="complianceIcon">🛡️</span>
          </div>

          <div class="complianceChips">
            {allergen_chips}
          </div>

          <form method="post"
                action="/app/wine/{int(wine_id)}/compliance/add-allergen"
                class="complianceInlineForm">
            <div>
              <label>Aggiungi allergene</label>
              <input class="input" name="name"
                     placeholder="es. solfiti, latte, uova..."
                     required>
            </div>

            <button class="btn" type="submit">Aggiungi allergene</button>
          </form>

          <div class="note" style="margin-top:14px">
            Se non è presente in elenco, viene salvato come testo libero.
          </div>
        </div>
      </div>

      <form id="saveForm" method="post" action="/app/wine/{int(wine_id)}/compliance/save">
        <div class="card compliancePanel" style="margin-top:18px">
          <div class="compliancePanelHead">
            <div>
              <div class="complianceSmallLabel">Extra ingredienti</div>
              <div class="h2">Testo libero ingredienti</div>
            </div>
            <span class="complianceIcon">✍️</span>
          </div>

          <label>Extra ingredienti</label>
          <input class="input" name="extra_ingredients"
                 value="{esc((meta.get('extra_ingredients') or '').strip())}"
                 placeholder="es. eventuali ingredienti non presenti in lista">
        </div>

        <div class="card compliancePanel" id="nutrizione" style="margin-top:18px">
          <div class="compliancePanelHead">
            <div>
              <div class="complianceSmallLabel">Nutrizione</div>
              <div class="h2">Valori nutrizionali</div>
            </div>

            <span class="pill pill-muted">kJ/kcal obbligatori</span>
          </div>

          <div class="note" style="margin-top:0">
            Valori riferiti a 100 ml. kJ e kcal sono obbligatori; virgola e punto sono entrambi accettati.
          </div>

          <div class="complianceNutritionGrid">
            <div>
              <label>Energia (kJ per 100 ml)*</label>
              <input class="input mono" name="energy_kj" inputmode="decimal" min="0" max="5000"
                     value="{esc(_val(nut.get('energy_kj')))}"
                     placeholder="0">
            </div>

            <div>
              <label>Energia (kcal per 100 ml)*</label>
              <input class="input mono" name="energy_kcal" inputmode="decimal" min="0" max="1200"
                     value="{esc(_val(nut.get('energy_kcal')))}"
                     placeholder="0">
            </div>

            <div>
              <label>Grassi</label>
              <input class="input mono" name="fat" inputmode="decimal" min="0" max="100"
                     value="{esc(_val(nut.get('fat')))}">
            </div>

            <div>
              <label>Saturi</label>
              <input class="input mono" name="saturates" inputmode="decimal" min="0" max="100"
                     value="{esc(_val(nut.get('saturates')))}">
            </div>

            <div>
              <label>Carboidrati</label>
              <input class="input mono" name="carbs" inputmode="decimal" min="0" max="100"
                     value="{esc(_val(nut.get('carbs')))}">
            </div>

            <div>
              <label>Zuccheri</label>
              <input class="input mono" name="sugars" inputmode="decimal" min="0" max="100"
                     value="{esc(_val(nut.get('sugars')))}">
            </div>

            <div>
              <label>Proteine</label>
              <input class="input mono" name="protein" inputmode="decimal" min="0" max="100"
                     value="{esc(_val(nut.get('protein')))}">
            </div>

            <div>
              <label>Sale</label>
              <input class="input mono" name="salt" inputmode="decimal" min="0" max="100"
                     value="{esc(_val(nut.get('salt')))}">
            </div>
          </div>
        </div>

        <div class="card compliancePanel" id="riciclabilita" style="margin-top:18px">
          <div class="compliancePanelHead">
            <div>
              <div class="complianceSmallLabel">Riciclabilità</div>
              <div class="h2">Componenti packaging</div>
            </div>

            <span class="pill pill-muted">Materiale e codice verificati</span>
          </div>

          <div class="complianceRecycleList">
            {rec_html}
          </div>
        </div>

        <div class="card compliancePanel" style="margin-top:18px">
          <div class="compliancePanelHead">
            <div>
              <div class="complianceSmallLabel">Pagina pubblica</div>
              <div class="h2">Stile pagina pubblica</div>
            </div>
            <span class="complianceIcon">🌐</span>
          </div>

          <div class="complianceGrid2">
            <div>
              <label>Stile pagina pubblica</label>
              <select name="public_theme">
                <option value="minimal" {"selected" if theme == "minimal" else ""}>Normativo</option>
                <option value="saas" {"selected" if theme == "saas" else ""}>Moderno</option>
                <option value="classic" {"selected" if theme == "classic" else ""}>Classico</option>
              </select>
            </div>

            <div>
              <label>Nota</label>
              <input class="input" value="Lo stile modifica solo la presentazione. La pagina resta senza pubblicità." disabled>
            </div>
          </div>

          <label>Descrizione opzionale</label>
          <textarea class="input" name="story_text" style="min-height:110px">{esc((meta.get("story_text") or "").strip())}</textarea>
        </div>

        <div class="complianceActions">
          <a class="btn" href="/app/wine/{int(wine_id)}/images">Indietro</a>
          <button class="btn" type="submit" name="continue_to" value="stay">Salva</button>
          <button class="btn btn-primary complianceSaveBtn" type="submit" name="continue_to" value="review">Salva e continua</button>
        </div>
      </form>

      <div class="card compliancePanel" id="controllo-finale" style="margin-top:18px">
        <div class="complianceSmallLabel">Step 6</div><div class="h2">Controllo finale</div>
        <p>Il Compliance Score mostra errori bloccanti, warning e collegamenti ai campi da correggere. Il gate server viene eseguito di nuovo quando pubblichi.</p>
        {summary_html}
      </div>
      <div class="card compliancePanel" id="pubblicazione" style="margin-top:18px">
        <div class="complianceSmallLabel">Step 7</div><div class="h2">Preview e pubblicazione</div>
        <div class="complianceActions">
          <a class="btn" href="/preview/{esc(w.get('slug') or '')}" target="_blank">Apri preview</a>
          <a class="btn btn-primary" href="/app/wine/{int(wine_id)}">Vai alla pubblicazione</a>
        </div>
      </div>

      <script>
      (() => {{
        const form=document.getElementById('saveForm'); if(!form) return;
        const storageKey='qrfacile:wine:{int(wine_id)}:draft';
        const status=document.createElement('div'); status.className='note'; status.style.marginTop='10px'; status.textContent='Tutte le modifiche sono salvate.';
        form.insertAdjacentElement('afterbegin',status);
        let dirty=false; let submitting=false;
        const fields=Array.from(document.querySelectorAll('input[name],select[name],textarea[name]')).filter(node=>node.type!=='file'&&node.name!=='csrf_token');
        const keyFor=node=>`${{node.form?.action||'page'}}::${{node.name}}`;
        if ({str((msg or '').startswith('Dati salvati correttamente')).lower()}) sessionStorage.removeItem(storageKey);
        else {{
          try {{ const draft=JSON.parse(sessionStorage.getItem(storageKey)||'{{}}'); fields.forEach(node=>{{if(Object.hasOwn(draft,keyFor(node))) node.value=draft[keyFor(node)]}}); }} catch (_) {{}}
        }}
        const remember=()=>{{
          dirty=true; status.textContent='Modifiche non salvate'; status.className='note note-warn';
          const draft={{}}; fields.forEach(node=>draft[keyFor(node)]=node.value); sessionStorage.setItem(storageKey,JSON.stringify(draft));
        }};
        fields.forEach(node=>{{node.addEventListener('input',remember);node.addEventListener('change',remember)}});
        form.addEventListener('submit',()=>{{submitting=true}});
        window.addEventListener('beforeunload',event=>{{if(dirty&&!submitting){{event.preventDefault();event.returnValue=''}}}});
      }})();
      </script>

      <style>
        .complianceWrap {{
          max-width:1180px;
          margin:0 auto;
        }}

        .complianceHero {{
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
          grid-template-columns:minmax(0,1.35fr) 320px;
          gap:24px;
          align-items:end;
        }}

        .complianceEyebrow {{
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

        .complianceMeta {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:16px;
        }}

        .complianceMeta span {{
          display:inline-flex;
          padding:8px 11px;
          border-radius:999px;
          background:rgba(255,255,255,.72);
          border:1px solid rgba(2,8,23,.07);
          color:#475569;
          font-size:12px;
          font-weight:850;
        }}

        .complianceMeta b {{
          color:#0f172a;
          margin-left:4px;
        }}

        .complianceSummaryBox {{
          margin-top:18px;
          border-radius:22px;
          padding:16px;
          box-shadow:0 12px 30px rgba(2,8,23,.04);
        }}

        .complianceSummaryBox.todo {{
          border:1px solid rgba(245,158,11,.24);
          background:rgba(255,251,235,.78);
        }}

        .complianceSummaryBox.ok {{
          border:1px solid rgba(20,184,166,.18);
          background:rgba(236,253,245,.82);
        }}

        .complianceSummaryHead {{
          display:flex;
          gap:12px;
          align-items:flex-start;
        }}

        .complianceSummaryDot {{
          width:13px;
          height:13px;
          border-radius:999px;
          margin-top:5px;
          flex:0 0 auto;
        }}

        .complianceSummaryBox.todo .complianceSummaryDot {{
          background:#f59e0b;
          box-shadow:0 0 0 5px rgba(245,158,11,.13);
        }}

        .complianceSummaryBox.ok .complianceSummaryDot {{
          background:#10b981;
          box-shadow:0 0 0 5px rgba(16,185,129,.13);
        }}

        .complianceSummaryTitle {{
          font-size:16px;
          font-weight:950;
          line-height:1.2;
        }}

        .complianceSummaryText {{
          margin-top:4px;
          color:#64748b;
          font-size:13px;
          font-weight:750;
          line-height:1.45;
        }}

        .complianceSummaryBlock {{
          margin-top:12px;
        }}

        .complianceSummaryLabel {{
          font-size:11px;
          font-weight:950;
          letter-spacing:.07em;
          text-transform:uppercase;
          color:#64748b;
          margin-bottom:8px;
        }}

        .complianceSummaryChips {{
          display:flex;
          gap:8px;
          flex-wrap:wrap;
        }}

        .complianceStatusChip {{
          display:inline-flex;
          align-items:center;
          gap:7px;
          padding:8px 11px;
          border-radius:999px;
          font-size:12px;
          font-weight:950;
        }}

        .complianceStatusChip b {{
          width:18px;
          height:18px;
          border-radius:999px;
          display:inline-flex;
          align-items:center;
          justify-content:center;
          color:#fff;
          font-size:11px;
          line-height:1;
        }}

        .complianceStatusChip.ok {{
          color:#0f766e;
          border:1px solid rgba(20,184,166,.16);
          background:rgba(236,253,245,.82);
        }}

        .complianceStatusChip.ok b {{
          background:#10b981;
        }}

        .complianceStatusChip.todo {{
          color:#92400e;
          border:1px solid rgba(245,158,11,.22);
          background:rgba(255,251,235,.88);
        }}

        .complianceStatusChip.todo b {{
          background:#f59e0b;
        }}

        .complianceOverrideRequest {{
          margin-top:14px;
          display:grid;
          grid-template-columns:minmax(0,1fr) auto;
          gap:12px;
          align-items:end;
          border-top:1px solid rgba(2,8,23,.08);
          padding-top:14px;
        }}

        .complianceOverrideRequest .btn {{
          border-color:rgba(245,158,11,.28);
          color:#92400e;
          font-weight:950;
          background:rgba(255,255,255,.72);
        }}

        @media(max-width:760px) {{
          .complianceOverrideRequest {{
            grid-template-columns:1fr;
          }}

          .complianceOverrideRequest .btn {{
            width:100%;
          }}
        }}

        .complianceHeroCard {{
          border:1px solid rgba(2,8,23,.08);
          background:rgba(255,255,255,.72);
          border-radius:24px;
          padding:18px;
          box-shadow:0 18px 45px rgba(2,8,23,.06);
        }}

        .complianceHeroCardTitle {{
          color:#64748b;
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.08em;
        }}

        .complianceStepsMini {{
          display:grid;
          gap:10px;
          margin-top:14px;
        }}

        .complianceStepsMini div {{
          display:flex;
          align-items:center;
          gap:10px;
          border:1px solid rgba(2,8,23,.07);
          border-radius:17px;
          padding:11px;
          background:rgba(255,255,255,.68);
        }}

        .complianceStepsMini div.active {{
          background:rgba(236,253,245,.90);
          border-color:rgba(20,184,166,.18);
        }}

        .complianceStepsMini b {{
          width:28px;
          height:28px;
          border-radius:11px;
          display:flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.92),rgba(207,232,255,.92));
        }}

        .complianceStepsMini span {{
          font-weight:900;
          font-size:13px;
        }}

        .complianceTabs {{
          display:flex;
          gap:10px;
          flex-wrap:wrap;
          margin-top:18px;
        }}

        .complianceTab {{
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

        .complianceTab.active {{
          background:linear-gradient(135deg,rgba(191,245,230,.95),rgba(207,232,255,.88));
          border-color:rgba(20,184,166,.18);
        }}

        .complianceFlow {{
          display:grid;
          grid-template-columns:repeat(3,minmax(0,1fr));
          gap:14px;
          margin-top:18px;
        }}

        .complianceFlow a {{
          display:flex;
          gap:12px;
          align-items:flex-start;
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          padding:16px;
          background:rgba(255,255,255,.78);
          box-shadow:0 12px 30px rgba(2,8,23,.04);
        }}

        .complianceFlow a.active {{
          background:linear-gradient(135deg,rgba(191,245,230,.78),rgba(207,232,255,.62));
          border-color:rgba(20,184,166,.18);
        }}

        .complianceFlow span {{
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

        .complianceFlow b {{
          display:block;
          font-size:15px;
          font-weight:950;
        }}

        .complianceFlow small {{
          display:block;
          margin-top:3px;
          color:#64748b;
          font-size:12px;
          font-weight:750;
          line-height:1.35;
        }}

        .complianceGrid2 {{
          display:grid;
          grid-template-columns:1fr 1fr;
          gap:18px;
          margin-top:18px;
        }}

        .compliancePanel {{
          padding:22px;
        }}

        .compliancePanelHead {{
          display:flex;
          justify-content:space-between;
          gap:14px;
          align-items:flex-start;
          margin-bottom:16px;
        }}

        .complianceIcon {{
          width:40px;
          height:40px;
          border-radius:16px;
          display:inline-flex;
          align-items:center;
          justify-content:center;
          background:linear-gradient(135deg,rgba(191,245,230,.88),rgba(207,232,255,.80));
          border:1px solid rgba(2,8,23,.07);
          font-size:19px;
          flex:0 0 auto;
        }}

        .complianceSmallLabel {{
          color:#64748b;
          font-size:12px;
          font-weight:950;
          text-transform:uppercase;
          letter-spacing:.08em;
        }}

        .complianceChips {{
          display:flex;
          gap:8px;
          flex-wrap:wrap;
          min-height:38px;
          align-items:center;
        }}

        .complianceChip {{
          display:inline-flex;
          align-items:center;
          padding:8px 11px;
          border-radius:999px;
          background:rgba(236,253,245,.82);
          border:1px solid rgba(20,184,166,.15);
          font-size:12px;
          font-weight:900;
          color:#0f766e;
        }}

        .complianceMuted {{
          color:#64748b;
          font-weight:750;
        }}

        .complianceInlineForm {{
          margin-top:16px;
          display:grid;
          grid-template-columns:minmax(0,1fr) auto;
          gap:12px;
          align-items:end;
        }}

        .complianceNutritionGrid {{
          display:grid;
          grid-template-columns:repeat(4,minmax(0,1fr));
          gap:14px;
          margin-top:16px;
        }}

        .complianceRecycleList {{
          display:grid;
          gap:14px;
        }}

        .complianceRecycleCard {{
          border:1px solid rgba(2,8,23,.08);
          border-radius:22px;
          padding:16px;
          background:rgba(255,255,255,.70);
        }}

        .complianceRecycleHead {{
          display:flex;
          justify-content:space-between;
          gap:14px;
          align-items:flex-start;
          margin-bottom:12px;
        }}

        .complianceRecycleGrid {{
          display:grid;
          grid-template-columns:1.2fr .8fr .8fr 1.2fr;
          gap:12px;
        }}

        .complianceActions {{
          margin-top:20px;
          display:flex;
          gap:12px;
          flex-wrap:wrap;
          align-items:center;
        }}

        .complianceSaveBtn {{
          min-width:220px;
        }}

        .complianceExportBtn {{
          border-color:rgba(20,184,166,.22);
          color:#0f766e;
          font-weight:950;
        }}

        @media(max-width:1050px) {{
          .complianceHero,
          .complianceGrid2 {{
            grid-template-columns:1fr;
          }}

          .complianceNutritionGrid {{
            grid-template-columns:repeat(2,minmax(0,1fr));
          }}

          .complianceRecycleGrid {{
            grid-template-columns:1fr 1fr;
          }}
        }}

        @media(max-width:760px) {{
          .complianceFlow {{
            grid-template-columns:1fr;
          }}

          .complianceInlineForm {{
            grid-template-columns:1fr;
          }}

          .complianceNutritionGrid,
          .complianceRecycleGrid {{
            grid-template-columns:1fr;
          }}
        }}

        @media(max-width:560px) {{
          .complianceHero,
          .compliancePanel {{
            padding:22px;
          }}

          .complianceActions .btn,
          .complianceInlineForm .btn {{
            width:100%;
          }}

          .compliancePanelHead,
          .complianceRecycleHead {{
            flex-direction:column;
            align-items:flex-start;
          }}
        }}
      </style>
    </section>
    """

    return HTMLResponse(page(
        title="QRFACILE · Compliance",
        subtitle="Compliance lotto",
        body_html=body,
        actions_html=actions,
        user_email=user.get("email", ""),
        role=role,
        credits=balances,
    ))


@router.post("/app/wine/{wine_id}/compliance/add-ingredient")
def add_ingredient(request: Request, wine_id: int, name: str = Form(...)):
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _wine(cur, int(wine_id))

    require_any_role(
        request,
        ("winery", "studio", "admin"),
        winery_id=int(w["winery_id"]),
        need="edit",
    )

    nm = (name or "").strip()

    if not nm:
        return _redirect(wine_id, "Ingrediente vuoto")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id FROM ingredients_master WHERE lower(name)=lower(%s) LIMIT 1",
                (nm,),
            )
            im = cur.fetchone()

            if im:
                cur.execute(
                    """
                    INSERT INTO wine_ingredients (wine_id, ingredient_id)
                    VALUES (%s,%s)
                    ON CONFLICT DO NOTHING
                    """,
                    (int(wine_id), int(im["id"])),
                )
            else:
                cur.execute(
                    "SELECT extra_ingredients, story_text, public_theme FROM wine_meta WHERE wine_id=%s LIMIT 1",
                    (int(wine_id),),
                )
                m = cur.fetchone() or {}
                extra = (m.get("extra_ingredients") or "").strip()

                if extra:
                    extra = extra + ", " + nm
                else:
                    extra = nm

                _upsert_meta(
                    cur,
                    int(wine_id),
                    extra,
                    (m.get("story_text") or ""),
                    (m.get("public_theme") or "minimal"),
                )

            conn.commit()

    return _redirect(wine_id, "Ingrediente aggiunto")


@router.post("/app/wine/{wine_id}/compliance/add-allergen")
def add_allergen(request: Request, wine_id: int, name: str = Form(...)):
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _wine(cur, int(wine_id))

    require_any_role(
        request,
        ("winery", "studio", "admin"),
        winery_id=int(w["winery_id"]),
        need="edit",
    )

    nm = (name or "").strip()

    if not nm:
        return _redirect(wine_id, "Allergene vuoto")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id FROM allergens_master WHERE lower(name)=lower(%s) LIMIT 1",
                (nm,),
            )
            am = cur.fetchone()

            if am:
                cur.execute(
                    """
                    INSERT INTO wine_allergens (wine_id, allergen_id)
                    VALUES (%s,%s)
                    """,
                    (int(wine_id), int(am["id"])),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO wine_allergens (wine_id, custom_text)
                    VALUES (%s,%s)
                    """,
                    (int(wine_id), nm),
                )

            conn.commit()

    return _redirect(wine_id, "Allergene aggiunto")


@router.post("/app/wine/{wine_id}/compliance/save")
def compliance_save(
    request: Request,
    wine_id: int,
    energy_kj: str = Form(""),
    energy_kcal: str = Form(""),
    fat: str = Form(""),
    saturates: str = Form(""),
    carbs: str = Form(""),
    sugars: str = Form(""),
    protein: str = Form(""),
    salt: str = Form(""),
    extra_ingredients: str = Form(""),
    story_text: str = Form(""),
    public_theme: str = Form("minimal"),

    rec_bottle_product: str = Form(""),
    rec_bottle_code: str = Form(""),
    rec_bottle_extra: str = Form(""),
    rec_bottle_note: str = Form(""),

    rec_closure_product: str = Form(""),
    rec_closure_code: str = Form(""),
    rec_closure_extra: str = Form(""),
    rec_closure_note: str = Form(""),

    rec_capsule_product: str = Form(""),
    rec_capsule_code: str = Form(""),
    rec_capsule_extra: str = Form(""),
    rec_capsule_note: str = Form(""),

    rec_label_product: str = Form(""),
    rec_label_code: str = Form(""),
    rec_label_extra: str = Form(""),
    rec_label_note: str = Form(""),

    rec_box_product: str = Form(""),
    rec_box_code: str = Form(""),
    rec_box_extra: str = Form(""),
    rec_box_note: str = Form(""),

    rec_other_product: str = Form(""),
    rec_other_code: str = Form(""),
    rec_other_extra: str = Form(""),
    rec_other_note: str = Form(""),
):
    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            w = _wine(cur, int(wine_id))

    require_any_role(
        request,
        ("winery", "studio", "admin"),
        winery_id=int(w["winery_id"]),
        need="edit",
    )

    try:
        ekj = int((energy_kj or "").strip())
        ekcal = int((energy_kcal or "").strip())
    except Exception:
        return _redirect(wine_id, "Energia kJ kcal obbligatoria e numerica")

    recycle_values = {
        "bottle": (rec_bottle_product, rec_bottle_code, rec_bottle_extra, rec_bottle_note),
        "closure": (rec_closure_product, rec_closure_code, rec_closure_extra, rec_closure_note),
        "capsule": (rec_capsule_product, rec_capsule_code, rec_capsule_extra, rec_capsule_note),
        "label": (rec_label_product, rec_label_code, rec_label_extra, rec_label_note),
        "box": (rec_box_product, rec_box_code, rec_box_extra, rec_box_note),
        "other": (rec_other_product, rec_other_code, rec_other_extra, rec_other_note),
    }

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            _upsert_nutrition(
                cur,
                int(wine_id),
                ekj,
                ekcal,
                fat,
                saturates,
                carbs,
                sugars,
                protein,
                salt,
            )

            _upsert_meta(
                cur,
                int(wine_id),
                (extra_ingredients or "").strip(),
                (story_text or "").strip(),
                (public_theme or "minimal").strip() or "minimal",
            )

            for key, _label in COMPONENTS:
                product, code, extra_code, note = recycle_values.get(key, ("", "", "", ""))
                _upsert_recycle_item(
                    cur,
                    int(wine_id),
                    key,
                    product,
                    code,
                    extra_code,
                    note,
                )

            conn.commit()

    return _redirect(wine_id, "Salvato")
