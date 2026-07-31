import time
import hashlib

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app.services.recycling_catalog import normalize_recycling_items
from qrfacile_app.services.wine_compliance_explainability import run_explainable_wine_compliance
from qrfacile_app import ui

router = APIRouter()

SUPPORTED_LOCALES = ("it", "en")

LOCALES = {
    "it": {
        "digital_wine_label": "Etichetta digitale vino",
        "mandatory_product_info": "Informazioni obbligatorie del prodotto",
        "product_info_page": "Pagina informativa prodotto",
        "vintage": "Annata",
        "lot": "Lotto",
        "format": "Formato",
        "alcohol": "Alcol",
        "ingredients": "Ingredienti",
        "declared_ingredients_list": "Elenco ingredienti dichiarati",
        "allergens": "Allergeni",
        "declared_substances": "Sostanze o prodotti dichiarati",
        "nutrition": "Valori nutrizionali",
        "nutrition_per_100ml": "Valori riferiti a 100 ml",
        "energy": "Energia",
        "fat": "Grassi",
        "saturates": "Saturi",
        "carbs": "Carboidrati",
        "sugars": "Zuccheri",
        "protein_salt": "Proteine / Sale",
        "recyclability": "Riciclabilità",
        "recycling_components": "Componenti e codici di conferimento",
        "packaging_component": "Componente packaging",
        "no_data": "Nessun dato inserito",
        "active_page": "Pagina attiva",
        "in_completion": "In completamento",
        "mandatory_data_incomplete": "Dati obbligatori non ancora completi",
        "technical_verification": "Questa pagina è raggiungibile per verifica tecnica. Risultano ancora da completare:",
        "digital_product_info": "Informazioni digitali del prodotto. Pagina destinata alla consultazione dei dati obbligatori del vino.",
        "technical_draft": "Bozza tecnica",
        "draft": "BOZZA",
        "incomplete": "INCOMPLETO",
        "data_to_check": "Dato da verificare",
        "field_check_warning": "Il campo {label} contiene parole che sembrano non coerenti con una scheda vino. Verificare prima dell'uso definitivo.",
        "missing_ingredients": "ingredienti",
        "missing_allergens": "allergeni",
        "missing_energy_kj": "energia kJ",
        "missing_energy_kcal": "energia kcal",
        "missing_recyclability": "riciclabilità",
        "wine": "Vino",
        "winery": "Cantina",
    },
    "en": {
        "digital_wine_label": "Digital wine label",
        "mandatory_product_info": "Mandatory product information",
        "product_info_page": "Product information page",
        "vintage": "Vintage",
        "lot": "Lot",
        "format": "Format",
        "alcohol": "Alcohol",
        "ingredients": "Ingredients",
        "declared_ingredients_list": "Declared ingredients list",
        "allergens": "Allergens",
        "declared_substances": "Declared substances or products",
        "nutrition": "Nutrition declaration",
        "nutrition_per_100ml": "Values per 100 ml",
        "energy": "Energy",
        "fat": "Fat",
        "saturates": "Saturates",
        "carbs": "Carbohydrates",
        "sugars": "Sugars",
        "protein_salt": "Protein / Salt",
        "recyclability": "Recyclability",
        "recycling_components": "Components and recycling codes",
        "packaging_component": "Packaging component",
        "no_data": "No data entered",
        "active_page": "Active page",
        "in_completion": "In completion",
        "mandatory_data_incomplete": "Mandatory data not yet complete",
        "technical_verification": "This page is reachable for technical verification. The following data still needs to be completed:",
        "digital_product_info": "Digital product information. Page intended for consultation of mandatory wine data.",
        "technical_draft": "Technical draft",
        "draft": "DRAFT",
        "incomplete": "INCOMPLETE",
        "data_to_check": "Data to check",
        "field_check_warning": "The {label} field contains words that do not seem consistent with a wine sheet. Please verify before final use.",
        "missing_ingredients": "ingredients",
        "missing_allergens": "allergens",
        "missing_energy_kj": "energy kJ",
        "missing_energy_kcal": "energy kcal",
        "missing_recyclability": "recyclability",
        "wine": "Wine",
        "winery": "Winery",
    },
}

COMP_LABELS = {
    "it": {
        "bottle": "Bottiglia",
        "closure": "Tappo",
        "capsule": "Capsula",
        "label": "Etichetta",
        "box": "Scatola",
        "other": "Altro",
    },
    "en": {
        "bottle": "Bottle",
        "closure": "Closure",
        "capsule": "Capsule",
        "label": "Label",
        "box": "Box",
        "other": "Other",
    },
}

ALLERGEN_LABELS = {
    "it": {
        "solfiti": "Solfiti",
        "sulphites": "Solfiti",
        "sulfites": "Solfiti",
        "uova": "Uova",
        "egg": "Uova",
        "eggs": "Uova",
        "latte": "Latte",
        "milk": "Latte",
    },
    "en": {
        "solfiti": "Sulphites",
        "sulphites": "Sulphites",
        "sulfites": "Sulphites",
        "uova": "Egg",
        "egg": "Egg",
        "eggs": "Egg",
        "latte": "Milk",
        "milk": "Milk",
    },
}


def now_epoch() -> int:
    return int(time.time())


def day_utc() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def fp_hash(request: Request) -> str:
    ip = (request.client.host if request.client else "") or ""
    ua = request.headers.get("user-agent", "") or ""
    lang = request.headers.get("accept-language", "") or ""
    return hashlib.sha256(f"{ip}|{ua}|{lang}".encode()).hexdigest()[:24]


def choose_language(request: Request) -> str:
    query_lang = (request.query_params.get("lang") or "").strip().lower()

    if query_lang in SUPPORTED_LOCALES:
        return query_lang

    accept_language = request.headers.get("accept-language", "") or ""
    preferred = []

    for idx, part in enumerate(accept_language.split(",")):
        chunks = [x.strip() for x in part.split(";") if x.strip()]

        if not chunks:
            continue

        code = chunks[0].lower()
        base = code.split("-", 1)[0]

        if base not in SUPPORTED_LOCALES:
            continue

        quality = 1.0

        for chunk in chunks[1:]:
            if not chunk.startswith("q="):
                continue

            try:
                quality = float(chunk[2:])
            except ValueError:
                quality = 0.0

        preferred.append((quality, -idx, base))

    if preferred:
        preferred.sort(reverse=True)
        return preferred[0][2]

    return "it"


def tr(locale: str, key: str) -> str:
    return LOCALES.get(locale, LOCALES["it"]).get(key, LOCALES["it"].get(key, key))


def track_scan(cur, slug: str, request: Request):
    day = day_utc()
    fp = fp_hash(request)
    ts = now_epoch()

    cur.execute(
        """
        INSERT INTO qr_scan_dedup(slug, day, fp_hash, created_at)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT (slug, day, fp_hash) DO NOTHING
        """,
        (slug, day, fp, ts),
    )

    if cur.rowcount == 1:
        cur.execute(
            """
            INSERT INTO qr_scans_daily(slug, day, scans)
            VALUES (%s,%s,1)
            ON CONFLICT (slug, day)
            DO UPDATE SET scans = qr_scans_daily.scans + 1
            """,
            (slug, day),
        )


def _pick_first_col(cur, table: str, candidates: list[str]) -> str | None:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    cols = {r["column_name"] for r in (cur.fetchall() or [])}

    for c in candidates:
        if c in cols:
            return c

    return None


def theme_palette(theme: str):
    t = (theme or "minimal").strip().lower()

    if t == "classic":
        return {
            "theme": "classic",
            "bg": "#f8f5ef",
            "surface": "#ffffff",
            "surface2": "#fbfaf7",
            "text": "#1f2933",
            "muted": "#667085",
            "line": "#e7ded0",
            "accent": "#7c2d12",
            "accent2": "#a16207",
            "soft": "#fff7ed",
        }

    if t in ("saas", "modern", "moderno"):
        return {
            "theme": "modern",
            "bg": "#f4fbf8",
            "surface": "#ffffff",
            "surface2": "#f8fffc",
            "text": "#0f172a",
            "muted": "#64748b",
            "line": "#dbece6",
            "accent": "#0f766e",
            "accent2": "#0ea5e9",
            "soft": "#ecfdf5",
        }

    return {
        "theme": "minimal",
        "bg": "#f8fafc",
        "surface": "#ffffff",
        "surface2": "#f9fafb",
        "text": "#111827",
        "muted": "#667085",
        "line": "#e5e7eb",
        "accent": "#0f766e",
        "accent2": "#155e75",
        "soft": "#ecfdf5",
    }



def _display_name(value: str) -> str:
    """
    Rende più leggibili valori arrivati come slug/nome file.
    Non modifica il DB, solo la visualizzazione.
    """
    v = (value or "").strip()
    if not v:
        return ""
    if "_" in v and " " not in v:
        v = v.replace("_", " ")
    return " ".join([part.capitalize() if part.islower() else part for part in v.split()])


def _upload_src(path: str) -> str:
    path = (path or "").strip()
    if not path:
        return ""
    if path.startswith("/uploads/"):
        return path
    if path.startswith("uploads/"):
        return "/" + path
    if path.startswith("/"):
        return path
    return "/uploads/" + path.lstrip("/")


def _is_suspicious_text(value: str) -> bool:
    v = (value or "").strip().lower()
    if not v:
        return False

    bad_words = [
        "corriere",
        "gls",
        "bartolini",
        "brt",
        "sda",
        "spedizione",
        "espresso",
        "trasporto",
        "fattura",
        "pagamento",
        "bonifico",
        "prova",
        "test",
    ]

    return any(x in v for x in bad_words)


def _suspicious_warning(label: str, value: str, locale: str) -> str:
    if not _is_suspicious_text(value):
        return ""

    warning = tr(locale, "field_check_warning").format(label=ui.esc(label))

    return f"""
    <div class="dataWarning">
      <b>{ui.esc(tr(locale, "data_to_check"))}</b>
      <span>{warning}</span>
    </div>
    """



def _fmt(x):
    return "—" if x is None or x == "" else str(x)


def _num(x):
    return ui.esc(_fmt(x))


COMP_ICON = {
    "bottle": "🍾",
    "closure": "🟤",
    "capsule": "🎗️",
    "label": "🏷️",
    "box": "📦",
    "other": "♻️",
}

COMP_TONE = {
    "bottle": "glass",
    "closure": "closure",
    "capsule": "capsule",
    "label": "paper",
    "box": "box",
    "other": "other",
}


def _session_role(request: Request) -> str:
    try:
        session = request.session
    except (AssertionError, RuntimeError):
        session = {}

    if not isinstance(session, dict):
        return ""

    candidates = [
        session.get("role"),
        session.get("user_role"),
        session.get("account_role"),
        session.get("account_type"),
        session.get("user_type"),
        session.get("type"),
    ]

    for key in ("user", "account"):
        nested = session.get(key)

        if isinstance(nested, dict):
            candidates.extend(
                [
                    nested.get("role"),
                    nested.get("user_role"),
                    nested.get("account_role"),
                    nested.get("account_type"),
                    nested.get("user_type"),
                    nested.get("type"),
                ]
            )

    if session.get("is_admin"):
        candidates.append("admin")

    for value in candidates:
        role = (str(value or "")).strip().lower()

        if role:
            return role

    return ""


def _require_preview_access(request: Request, cur, qr_row: dict):
    user = require_any_role(request, ("winery", "studio", "admin"))
    role = (user.get("role") or "").lower().strip()
    uid = int(user.get("id") or user.get("user_id") or 0)
    winery_id = int(qr_row.get("winery_id") or 0)

    if role == "admin":
        cur.execute(
            "SELECT admin_active_winery_id FROM users WHERE id=%s LIMIT 1",
            (uid,),
        )
        r = cur.fetchone() or {}
        active = r.get("admin_active_winery_id")
        if not active or int(active) == winery_id:
            return user
        raise HTTPException(403, "Preview non autorizzata per questa cantina")

    if role == "winery":
        if uid == int(qr_row.get("owner_user_id") or 0):
            return user
        raise HTTPException(403, "Preview non autorizzata")

    if role == "studio":
        cur.execute(
            """
            SELECT 1
            FROM studio_clients
            WHERE studio_user_id=%s
              AND winery_id=%s
              AND can_view=TRUE
            LIMIT 1
            """,
            (uid, winery_id),
        )
        if cur.fetchone():
            return user
        raise HTTPException(403, "Preview non autorizzata")

    raise HTTPException(403, "Preview non autorizzata")


def _label_missing(locale: str, ingredient_text: str, allergens: list[str], nut: dict, recycle_rows: list[dict]) -> list[str]:
    missing = []

    if not ingredient_text:
        missing.append(tr(locale, "missing_ingredients"))
    if not allergens:
        missing.append(tr(locale, "missing_allergens"))
    if nut.get("energy_kj") is None:
        missing.append(tr(locale, "missing_energy_kj"))
    if nut.get("energy_kcal") is None:
        missing.append(tr(locale, "missing_energy_kcal"))
    if not recycle_rows:
        missing.append(tr(locale, "missing_recyclability"))

    return missing


def _public_gate_allows(status: str, missing: list[str], compliance_report: dict) -> bool:
    return status == "attiva" and not missing and bool(compliance_report.get("publishable"))


def _render_label_page(request: Request, slug: str, *, preview: bool):
    slug = (slug or "").strip()
    locale = choose_language(request)

    if not slug:
        raise HTTPException(404, "Not found")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    qi.id AS qr_item_id,
                    qi.status,
                    qi.slug,
                    qw.id AS wine_id,
                    qw.winery_id,
                    w.owner_user_id,
                    qw.wine_name,
                    qw.vintage,
                    qw.lot,
                    qw.alcohol,
                    qw.volume_ml,
                    w.name AS winery_name,
                    w.logo_path,
                    COALESCE(wm.public_theme, 'minimal') AS public_theme,
                    COALESCE(wm.extra_ingredients, '') AS extra_ingredients
                FROM qr_items qi
                JOIN qr_wines qw ON qw.qr_item_id = qi.id
                JOIN wineries w ON w.id = qw.winery_id
                LEFT JOIN wine_meta wm ON wm.wine_id = qw.id
                WHERE qi.slug=%s
                LIMIT 1
                """,
                (slug,),
            )
            row = cur.fetchone()

            if not row:
                raise HTTPException(404, "QR not found")

            if preview:
                _require_preview_access(request, cur, row)

            status = (row.get("status") or "").strip().lower()
            if not preview and status != "attiva":
                raise HTTPException(404, "QR non pubblicato")
            is_draft = status != "attiva"

            cur.execute(
                """
                SELECT energy_kj, energy_kcal, fat, saturates, carbs, sugars, protein, salt
                FROM wine_nutrition
                WHERE wine_id=%s
                LIMIT 1
                """,
                (int(row["wine_id"]),),
            )
            nut = cur.fetchone() or {}

            ing_col = _pick_first_col(cur, "ingredients_master", ["name", "title", "label", "text", "description"])
            ingredients = []

            if ing_col:
                cur.execute(
                    f"""
                    SELECT im.{ing_col} AS label
                    FROM wine_ingredients wi
                    JOIN ingredients_master im ON im.id = wi.ingredient_id
                    WHERE wi.wine_id=%s
                    ORDER BY im.{ing_col}
                    LIMIT 800
                    """,
                    (int(row["wine_id"]),),
                )
                ingredients = [r["label"] for r in (cur.fetchall() or []) if r.get("label")]

            extra_ing = (row.get("extra_ingredients") or "").strip()

            all_col = _pick_first_col(cur, "allergens_master", ["name", "title", "label", "text", "description"])

            if all_col:
                cur.execute(
                    f"""
                    SELECT COALESCE(am.{all_col}, wa.custom_text) AS name
                    FROM wine_allergens wa
                    LEFT JOIN allergens_master am ON am.id = wa.allergen_id
                    WHERE wa.wine_id=%s
                    ORDER BY COALESCE(am.{all_col}, wa.custom_text)
                    """,
                    (int(row["wine_id"]),),
                )
            else:
                cur.execute(
                    """
                    SELECT wa.custom_text AS name
                    FROM wine_allergens wa
                    WHERE wa.wine_id=%s
                    ORDER BY wa.custom_text
                    """,
                    (int(row["wine_id"]),),
                )

            allergens_list = [r["name"] for r in (cur.fetchall() or []) if r.get("name")]

            cur.execute(
                """
                SELECT contains_sulfites, contains_egg, contains_milk
                FROM qr_wines
                WHERE id=%s
                LIMIT 1
                """,
                (int(row["wine_id"]),),
            )
            flags = cur.fetchone() or {}

            if flags.get("contains_sulfites"):
                allergens_list.append("solfiti")
            if flags.get("contains_egg"):
                allergens_list.append("uova")
            if flags.get("contains_milk"):
                allergens_list.append("latte")

            seen = set()
            allergens = []

            for a in allergens_list:
                k = (a or "").strip().lower()
                if not k or k in seen:
                    continue
                seen.add(k)
                allergens.append(a.strip())

            cur.execute(
                """
                SELECT component, product, code, extra_code, note
                FROM wine_recycle_items
                WHERE wine_id=%s
                ORDER BY component ASC
                """,
                (int(row["wine_id"]),),
            )
            recycle_rows = list(normalize_recycling_items({
                item["component"]: dict(item)
                for item in (cur.fetchall() or [])
            }).values())

            cur.execute(
                """
                SELECT kind, img_thumb, img_optimized
                FROM wine_assets
                WHERE wine_id=%s
                  AND kind IN ('front', 'back')
                ORDER BY CASE kind WHEN 'front' THEN 1 WHEN 'back' THEN 2 ELSE 3 END
                """,
                (int(row["wine_id"]),),
            )
            image_rows = cur.fetchall() or []

        conn.commit()

    pal = theme_palette(row.get("public_theme"))

    wine_name = _display_name(row.get("wine_name") or tr(locale, "wine"))
    winery_name = _display_name(row.get("winery_name") or tr(locale, "winery"))
    vintage = row.get("vintage") or ""
    lot = row.get("lot") or ""
    alcohol = row.get("alcohol") or ""
    volume_ml = row.get("volume_ml") or ""
    logo_path = row.get("logo_path") or ""

    ingredient_text = ", ".join([i for i in ingredients if i]) if ingredients else ""

    if extra_ing:
        ingredient_text = ingredient_text + (", " if ingredient_text else "") + extra_ing

    public_missing = _label_missing(locale, ingredient_text, allergens, nut, recycle_rows)
    is_incomplete = bool(public_missing)

    compliance_payload = {
        "wine": dict(row),
        "nutrition": dict(nut),
        "ingredients": ingredients,
        "allergens": allergens,
        "recycle": {item["component"]: dict(item) for item in recycle_rows},
        "meta": {"extra_ingredients": extra_ing},
    }
    compliance_report = run_explainable_wine_compliance(compliance_payload)
    if not preview and not _public_gate_allows(status, public_missing, compliance_report):
        raise HTTPException(404, "QR non conforme o incompleto")

    if not preview:
        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                try:
                    track_scan(cur, slug, request)
                except Exception:
                    pass
            conn.commit()

    if is_draft:
        status_label = tr(locale, "technical_draft")
        status_class = "draft"
    elif is_incomplete:
        status_label = tr(locale, "in_completion")
        status_class = "warning"
    else:
        status_label = tr(locale, "active_page")
        status_class = "active"

    logo_html = ""

    if logo_path:
        src = _upload_src(logo_path)
        logo_html = f"""
        <div class="producerLogo">
          <img src="{ui.esc(src)}" alt="Logo {ui.esc(winery_name)}">
        </div>
        """

    label_images_html = ""
    image_cards = []
    for image_row in image_rows:
        kind = (image_row.get("kind") or "").strip().lower()
        img_path = (image_row.get("img_optimized") or image_row.get("img_thumb") or "").strip()
        if not img_path:
            continue
        label = "Fronte etichetta" if kind == "front" else "Retro etichetta"
        image_cards.append(f"""
        <figure class="labelImageCard">
          <img src="{ui.esc(_upload_src(img_path))}" alt="{ui.esc(label)} {ui.esc(wine_name)}">
          <figcaption>{ui.esc(label)}</figcaption>
        </figure>
        """)

    if image_cards:
        label_images_html = f"""
        <section class="labelImages" aria-label="Immagini etichetta">
          {''.join(image_cards)}
        </section>
        """

    allergens_html = ""

    if allergens:
        allergens_html = "".join(
            [
                f"<span class='chip strong'>{ui.esc(ALLERGEN_LABELS.get(locale, ALLERGEN_LABELS['it']).get(a.lower(), a))}</span>"
                for a in allergens
            ]
        )
    else:
        allergens_html = f"<span class='empty'>{ui.esc(tr(locale, 'no_data'))}</span>"

    ingredient_warning_html = ""
    allergen_warning_html = ""

    if preview:
        ingredient_warning_html = _suspicious_warning(tr(locale, "ingredients").lower(), ingredient_text, locale)
        allergen_warning_html = _suspicious_warning(tr(locale, "allergens").lower(), ", ".join(allergens), locale)

    grouped = {}

    for r in recycle_rows:
        comp = (r.get("component") or "").strip().lower()
        grouped[comp] = r

    rec_cards = []

    for comp in ["bottle", "closure", "capsule", "label", "box", "other"]:
        r = grouped.get(comp)

        if not r:
            continue

        product = (r.get("product") or "").strip()
        code = (r.get("code") or "").strip()
        extra = (r.get("extra_code") or "").strip()
        note = (r.get("note") or "").strip()
        codes = ", ".join([c for c in [code, extra] if c])

        code_html = f"<span class='materialCode'>{ui.esc(codes)}</span>" if codes else ""
        note_html = f"<div class='noteText'>{ui.esc(note)}</div>" if note else ""

        icon = COMP_ICON.get(comp, "♻️")
        tone = COMP_TONE.get(comp, "other")
        comp_label = COMP_LABELS.get(locale, COMP_LABELS["it"]).get(comp, comp.title())

        rec_cards.append(
            f"""
            <div class="recycleItem recycleTone-{ui.esc(tone)}">
              <div class="recycleTop">
                <div class="recycleNameWrap">
                    <span class="recycleIcon">{ui.esc(icon)}</span>
                  <div>
                    <div class="recycleName">{ui.esc(comp_label)}</div>
                    <div class="recycleHint">{ui.esc(tr(locale, "packaging_component"))}</div>
                  </div>
                </div>
                {code_html}
              </div>
              <div class="recycleProduct">{ui.esc(product) if product else "—"}</div>
              {note_html}
            </div>
            """
        )

    recycle_html = "".join(rec_cards) if rec_cards else f"<span class='empty'>{ui.esc(tr(locale, 'no_data'))}</span>"

    n_energy = f"{_num(nut.get('energy_kj'))} kJ / {_num(nut.get('energy_kcal'))} kcal"
    n_fat = _num(nut.get("fat"))
    n_sat = _num(nut.get("saturates"))
    n_carbs = _num(nut.get("carbs"))
    n_sug = _num(nut.get("sugars"))
    n_prot = _num(nut.get("protein"))
    n_salt = _num(nut.get("salt"))

    warning_html = ""
    qr_definitive_notice = ""

    if preview:
        qr_definitive_notice = """
        <section class="warningBox" style="border-color:rgba(20,184,166,.26);background:rgba(240,253,250,.92)">
          <div class="warningIcon">i</div>
          <div>
            <div class="warningTitle">QR definitivo</div>
            <div class="warningText">
              Il QR generato è già quello definitivo e può essere inviato immediatamente al tipografo. La pagina pubblica non sarà visibile finché non saranno completati tutti i dati obbligatori e la pubblicazione non sarà confermata.
            </div>
          </div>
        </section>
        """

    if preview and is_incomplete:
        warning_html = f"""
        <section class="warningBox">
          <div class="warningIcon">!</div>
          <div>
            <div class="warningTitle">{ui.esc(tr(locale, "mandatory_data_incomplete"))}</div>
            <div class="warningText">
              {ui.esc(tr(locale, "technical_verification"))}
              <b>{ui.esc(", ".join(public_missing))}</b>.
            </div>
          </div>
        </section>
        """

    watermark = ""

    if preview and is_draft:
        watermark = f"<div class='watermark'>{ui.esc(tr(locale, 'draft'))}</div>"
    elif preview and is_incomplete:
        watermark = f"<div class='watermark'>{ui.esc(tr(locale, 'incomplete'))}</div>"

    lang_links = []

    for lang_code in SUPPORTED_LOCALES:
        active = " active" if lang_code == locale else ""
        lang_links.append(
            f"<a class='langLink{active}' href='/{'preview' if preview else 'e'}/{ui.esc(slug)}?lang={lang_code}' hreflang='{lang_code}'>{lang_code.upper()}</a>"
        )

    language_selector = "<nav class='languageSwitch' aria-label='Language'>" + "".join(lang_links) + "</nav>"

    html = f"""<!doctype html>
<html lang="{ui.esc(locale)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{ui.esc(wine_name)} · {ui.esc(winery_name)}</title>
<meta name="robots" content="noindex,nofollow">
<style>
:root {{
  --bg:{pal["bg"]};
  --surface:{pal["surface"]};
  --surface2:{pal["surface2"]};
  --text:{pal["text"]};
  --muted:{pal["muted"]};
  --line:{pal["line"]};
  --accent:{pal["accent"]};
  --accent2:{pal["accent2"]};
  --soft:{pal["soft"]};
}}

* {{
  box-sizing:border-box;
}}

body {{
  margin:0;
  font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  background:
    radial-gradient(circle at 0% 0%, rgba(20,184,166,.12), transparent 30%),
    radial-gradient(circle at 100% 0%, rgba(14,165,233,.10), transparent 30%),
    var(--bg);
  color:var(--text);
}}

.page {{
  width:100%;
  max-width:980px;
  margin:0 auto;
  padding:18px;
}}

.header {{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  margin-bottom:14px;
}}

.brandMini {{
  display:flex;
  align-items:center;
  gap:10px;
  min-width:0;
}}

.brandMark {{
  width:42px;
  height:42px;
  border-radius:15px;
  background:#ffffff;
  border:1px solid var(--line);
  box-shadow:0 14px 34px rgba(15,118,110,.12);
  display:flex;
  align-items:center;
  justify-content:center;
  overflow:hidden;
  flex:0 0 auto;
}}

.brandMark img {{
  width:30px;
  height:30px;
  display:block;
  object-fit:contain;
}}

.brandInlineLogo {{
  width:34px;
  height:34px;
  display:block;
  flex:0 0 auto;
}}

.brandText {{
  min-width:0;
}}

.brandText b {{
  display:block;
  font-size:14px;
  font-weight:900;
  line-height:1.15;
}}

.brandText span {{
  display:block;
  margin-top:2px;
  color:var(--muted);
  font-size:12px;
  font-weight:700;
}}

.statusBadge {{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding:9px 12px;
  border-radius:999px;
  border:1px solid var(--line);
  background:rgba(255,255,255,.70);
  color:var(--muted);
  font-size:12px;
  font-weight:900;
  white-space:nowrap;
}}

.headerActions {{
  display:flex;
  align-items:center;
  gap:10px;
  flex:0 0 auto;
}}

.languageSwitch {{
  display:inline-flex;
  align-items:center;
  gap:2px;
  padding:3px;
  border:1px solid var(--line);
  border-radius:999px;
  background:rgba(255,255,255,.70);
}}

.langLink {{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:38px;
  height:30px;
  padding:0 10px;
  border-radius:999px;
  color:var(--muted);
  text-decoration:none;
  font-size:12px;
  font-weight:950;
}}

.langLink.active {{
  background:var(--accent);
  color:#ffffff;
}}

.statusBadge::before {{
  content:"";
  width:9px;
  height:9px;
  border-radius:999px;
  background:var(--accent);
  box-shadow:0 0 0 4px rgba(20,184,166,.13);
}}

.statusBadge.warning::before {{
  background:#f59e0b;
  box-shadow:0 0 0 4px rgba(245,158,11,.14);
}}

.statusBadge.draft::before {{
  background:#64748b;
  box-shadow:0 0 0 4px rgba(100,116,139,.14);
}}

.hero {{
  position:relative;
  overflow:hidden;
  border:1px solid var(--line);
  border-radius:28px;
  background:
    radial-gradient(circle at 14% 12%, rgba(20,184,166,.14), transparent 28%),
    radial-gradient(circle at 90% 0%, rgba(14,165,233,.12), transparent 32%),
    linear-gradient(135deg, rgba(255,255,255,.98), rgba(255,255,255,.88));
  box-shadow:0 24px 80px rgba(2,8,23,.08);
  padding:24px;
}}

.producerLogo {{
  margin-bottom:16px;
}}

.producerLogo img {{
  max-height:58px;
  max-width:220px;
  object-fit:contain;
  display:block;
}}

.labelImages {{
  margin-top:18px;
  display:grid;
  grid-template-columns:repeat(2, minmax(0, 1fr));
  gap:14px;
}}

.labelImageCard {{
  margin:0;
  border:1px solid var(--line);
  border-radius:22px;
  background:rgba(255,255,255,.74);
  overflow:hidden;
}}

.labelImageCard img {{
  width:100%;
  aspect-ratio:4 / 5;
  object-fit:contain;
  display:block;
  background:#fff;
}}

.labelImageCard figcaption {{
  padding:10px 12px;
  color:var(--muted);
  font-size:12px;
  font-weight:850;
}}

.eyebrow {{
  display:inline-flex;
  padding:7px 11px;
  border-radius:999px;
  background:var(--soft);
  color:var(--accent);
  border:1px solid rgba(15,118,110,.12);
  font-size:11px;
  font-weight:950;
  letter-spacing:.08em;
  text-transform:uppercase;
}}

.title {{
  margin:14px 0 0;
  font-size:clamp(31px, 6vw, 54px);
  line-height:.98;
  font-weight:950;
  letter-spacing:-1.8px;
}}

.subtitle {{
  margin-top:13px;
  color:var(--muted);
  font-size:15px;
  font-weight:720;
  line-height:1.55;
}}

.metaGrid {{
  margin-top:18px;
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:10px;
}}

.metaItem {{
  border:1px solid var(--line);
  background:rgba(255,255,255,.72);
  border-radius:18px;
  padding:12px;
}}

.metaItem span {{
  display:block;
  color:var(--muted);
  font-size:11px;
  font-weight:950;
  text-transform:uppercase;
  letter-spacing:.06em;
}}

.metaItem b {{
  display:block;
  margin-top:5px;
  font-size:15px;
  font-weight:920;
  overflow:hidden;
  text-overflow:ellipsis;
}}

.warningBox {{
  margin-top:16px;
  display:flex;
  gap:12px;
  align-items:flex-start;
  border:1px solid rgba(245,158,11,.25);
  background:rgba(255,251,235,.82);
  border-radius:20px;
  padding:15px;
}}

.warningIcon {{
  width:31px;
  height:31px;
  border-radius:12px;
  display:flex;
  align-items:center;
  justify-content:center;
  background:#f59e0b;
  color:white;
  font-weight:950;
  flex:0 0 auto;
}}

.warningTitle {{
  font-size:15px;
  font-weight:950;
  color:#92400e;
}}

.warningText {{
  margin-top:4px;
  color:#78350f;
  font-size:13px;
  font-weight:720;
  line-height:1.45;
}}

.contentGrid {{
  margin-top:16px;
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:14px;
}}

.infoCard {{
  border:1px solid var(--line);
  border-radius:24px;
  background:rgba(255,255,255,.86);
  box-shadow:0 14px 45px rgba(2,8,23,.055);
  padding:18px;
}}

.infoCard.full {{
  grid-column:1 / -1;
}}

.cardHead {{
  display:flex;
  align-items:flex-start;
  justify-content:space-between;
  gap:10px;
  margin-bottom:13px;
}}

.cardTitle {{
  font-size:18px;
  font-weight:950;
  letter-spacing:-.25px;
}}

.cardSub {{
  margin-top:3px;
  color:var(--muted);
  font-size:12px;
  font-weight:760;
}}

.cardIcon {{
  width:38px;
  height:38px;
  border-radius:15px;
  display:flex;
  align-items:center;
  justify-content:center;
  background:linear-gradient(135deg, rgba(20,184,166,.14), rgba(14,165,233,.11));
  border:1px solid var(--line);
  font-size:18px;
  flex:0 0 auto;
}}

.textValue {{
  color:#334155;
  font-size:15px;
  line-height:1.65;
  font-weight:650;
}}

.dataWarning {{
  margin-top:12px;
  border:1px solid rgba(245,158,11,.24);
  background:rgba(255,251,235,.86);
  color:#92400e;
  border-radius:16px;
  padding:12px;
}}

.dataWarning b {{
  display:block;
  font-size:13px;
  font-weight:950;
}}

.dataWarning span {{
  display:block;
  margin-top:4px;
  font-size:12px;
  font-weight:750;
  line-height:1.4;
}}

.empty {{
  color:var(--muted);
  font-weight:720;
}}

.chips {{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
}}

.chip {{
  display:inline-flex;
  align-items:center;
  padding:9px 12px;
  border-radius:999px;
  border:1px solid var(--line);
  background:var(--surface2);
  color:#334155;
  font-size:13px;
  font-weight:880;
}}

.chip.strong {{
  background:var(--soft);
  color:var(--accent);
  border-color:rgba(15,118,110,.13);
}}

.nutritionGrid {{
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:10px;
}}

.nutritionItem {{
  border:1px solid var(--line);
  border-radius:18px;
  background:var(--surface2);
  padding:13px;
}}

.nutritionItem span {{
  display:block;
  color:var(--muted);
  font-size:11px;
  font-weight:950;
  text-transform:uppercase;
  letter-spacing:.06em;
}}

.nutritionItem b {{
  display:block;
  margin-top:6px;
  font-size:14px;
  line-height:1.35;
  font-weight:920;
}}

.recycleGrid {{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:10px;
}}

.recycleItem {{
  border:1px solid var(--line);
  border-radius:20px;
  background:var(--surface2);
  padding:14px;
  position:relative;
  overflow:hidden;
}}

.recycleItem::before {{
  content:"";
  position:absolute;
  inset:0 auto 0 0;
  width:5px;
  background:var(--accent);
  opacity:.55;
}}

.recycleTone-glass {{
  background:linear-gradient(135deg, rgba(236,253,245,.88), rgba(255,255,255,.92));
}}

.recycleTone-closure {{
  background:linear-gradient(135deg, rgba(254,243,199,.72), rgba(255,255,255,.92));
}}

.recycleTone-capsule {{
  background:linear-gradient(135deg, rgba(239,246,255,.82), rgba(255,255,255,.92));
}}

.recycleTone-paper {{
  background:linear-gradient(135deg, rgba(250,250,249,.95), rgba(255,255,255,.92));
}}

.recycleTone-box {{
  background:linear-gradient(135deg, rgba(255,247,237,.86), rgba(255,255,255,.92));
}}

.recycleTone-other {{
  background:linear-gradient(135deg, rgba(245,243,255,.75), rgba(255,255,255,.92));
}}

.recycleTop {{
  display:flex;
  justify-content:space-between;
  gap:10px;
  align-items:flex-start;
  flex-wrap:wrap;
  position:relative;
  z-index:1;
}}

.recycleNameWrap {{
  display:flex;
  align-items:flex-start;
  gap:10px;
}}

.recycleIcon {{
  width:34px;
  height:34px;
  border-radius:13px;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  background:#ffffff;
  border:1px solid var(--line);
  box-shadow:0 8px 20px rgba(2,8,23,.05);
  font-size:17px;
  flex:0 0 auto;
}}

.recycleName {{
  font-size:14px;
  font-weight:950;
}}

.recycleHint {{
  margin-top:2px;
  color:var(--muted);
  font-size:11px;
  font-weight:800;
}}

.materialCode {{
  display:inline-flex;
  padding:7px 10px;
  border-radius:999px;
  background:#ffffff;
  color:var(--accent);
  font-size:12px;
  font-weight:950;
  border:1px solid rgba(15,118,110,.14);
  box-shadow:0 6px 16px rgba(2,8,23,.04);
}}

.recycleProduct {{
  position:relative;
  z-index:1;
  margin-top:10px;
  color:#334155;
  font-size:13px;
  font-weight:760;
  line-height:1.4;
}}

.noteText {{
  margin-top:7px;
  color:var(--muted);
  font-size:12px;
  line-height:1.4;
}}

.footerNote {{
  margin-top:14px;
  border:1px solid var(--line);
  border-radius:22px;
  background:rgba(255,255,255,.70);
  padding:14px;
  color:var(--muted);
  font-size:12px;
  font-weight:720;
  line-height:1.5;
  text-align:center;
}}

.watermark {{
  position:fixed;
  inset:0;
  pointer-events:none;
  display:flex;
  align-items:center;
  justify-content:center;
  opacity:.055;
  font-size:clamp(44px, 14vw, 120px);
  font-weight:950;
  transform:rotate(-18deg);
  color:#0f172a;
  z-index:20;
}}

@media(max-width:760px) {{
  .page {{
    padding:12px;
  }}

  .header {{
    align-items:flex-start;
  }}

  .headerActions {{
    flex-direction:column-reverse;
    align-items:flex-end;
  }}

  .statusBadge {{
    font-size:11px;
    padding:8px 10px;
  }}

  .hero {{
    border-radius:24px;
    padding:20px;
  }}

  .metaGrid {{
    grid-template-columns:1fr 1fr;
  }}

  .contentGrid,
  .labelImages {{
    grid-template-columns:1fr;
  }}

  .infoCard.full {{
    grid-column:auto;
  }}

  .nutritionGrid {{
    grid-template-columns:1fr 1fr;
  }}

  .recycleGrid {{
    grid-template-columns:1fr;
  }}
}}

@media(max-width:430px) {{
  .brandText span {{
    display:none;
  }}

  .metaGrid,
  .nutritionGrid {{
    grid-template-columns:1fr;
  }}

  .title {{
    letter-spacing:-1.2px;
  }}
}}
</style>
</head>
<body>
{watermark}

<div class="page">
  <header class="header">
    <div class="brandMini">
      <div class="brandMark">
      <svg width="42" height="42" viewBox="0 0 54 54" xmlns="http://www.w3.org/2000/svg" class="brandInlineLogo">
        <rect width="54" height="54" rx="17" fill="#0f766e"/>
        <rect x="11" y="12" width="11" height="11" rx="3" fill="#ffffff"/>
        <rect x="32" y="12" width="11" height="11" rx="3" fill="#ffffff"/>
        <rect x="11" y="32" width="11" height="11" rx="3" fill="#ffffff"/>
        <rect x="28" y="28" width="7" height="7" rx="2" fill="#ffffff"/>
        <rect x="38" y="28" width="5" height="5" rx="2" fill="#ffffff"/>
        <rect x="28" y="38" width="15" height="5" rx="2" fill="#ffffff"/>
        <path d="M27 8C27 8 22 15 22 20C22 24 24 27 27 27C30 27 32 24 32 20C32 15 27 8 27 8Z" fill="#ffffff"/>
        <path d="M24.5 20.5L26.6 22.6L30.8 17.6" stroke="#0f766e" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      </div>
    <div class="brandText">
        <b>{ui.esc(tr(locale, "digital_wine_label"))}</b>
        <span>{ui.esc(tr(locale, "mandatory_product_info"))}</span>
      </div>
    </div>

    <div class="headerActions">
      {language_selector}
      <div class="statusBadge {status_class}">
        {ui.esc(status_label)}
      </div>
    </div>
  </header>

  <section class="hero">
    {logo_html}

    <div class="eyebrow">{ui.esc(tr(locale, "product_info_page"))}</div>

    <h1 class="title">{ui.esc(wine_name)}</h1>

    <div class="subtitle">
      {ui.esc(winery_name)}
    </div>

    <div class="metaGrid">
      <div class="metaItem">
        <span>{ui.esc(tr(locale, "vintage"))}</span>
        <b>{ui.esc(str(vintage)) if vintage else "—"}</b>
      </div>

      <div class="metaItem">
        <span>{ui.esc(tr(locale, "lot"))}</span>
        <b>{ui.esc(str(lot)) if lot else "—"}</b>
      </div>

      <div class="metaItem">
        <span>{ui.esc(tr(locale, "format"))}</span>
        <b>{ui.esc(str(volume_ml)) if volume_ml else "—"} ml</b>
      </div>

      <div class="metaItem">
        <span>{ui.esc(tr(locale, "alcohol"))}</span>
        <b>{ui.esc(str(alcohol)) if alcohol else "—"}%</b>
      </div>
    </div>

    {label_images_html}
    {qr_definitive_notice}
    {warning_html}
  </section>

  <main class="contentGrid">
    <section class="infoCard">
      <div class="cardHead">
        <div>
          <div class="cardTitle">{ui.esc(tr(locale, "ingredients"))}</div>
          <div class="cardSub">{ui.esc(tr(locale, "declared_ingredients_list"))}</div>
        </div>
        <div class="cardIcon">🍇</div>
      </div>

      <div class="textValue">
        {ui.esc(ingredient_text) if ingredient_text else f"<span class='empty'>{ui.esc(tr(locale, 'no_data'))}</span>"}
      </div>
      {ingredient_warning_html}
    </section>

    <section class="infoCard">
      <div class="cardHead">
        <div>
          <div class="cardTitle">{ui.esc(tr(locale, "allergens"))}</div>
          <div class="cardSub">{ui.esc(tr(locale, "declared_substances"))}</div>
        </div>
        <div class="cardIcon">🛡️</div>
      </div>

      <div class="chips">
        {allergens_html}
      </div>
      {allergen_warning_html}
    </section>

    <section class="infoCard full">
      <div class="cardHead">
        <div>
          <div class="cardTitle">{ui.esc(tr(locale, "nutrition"))}</div>
          <div class="cardSub">{ui.esc(tr(locale, "nutrition_per_100ml"))}</div>
        </div>
        <div class="cardIcon">⚖️</div>
      </div>

      <div class="nutritionGrid">
        <div class="nutritionItem">
          <span>{ui.esc(tr(locale, "energy"))}</span>
          <b>{n_energy}</b>
        </div>

        <div class="nutritionItem">
          <span>{ui.esc(tr(locale, "fat"))}</span>
          <b>{n_fat} g<br><small>{ui.esc(tr(locale, "saturates"))} {n_sat} g</small></b>
        </div>

        <div class="nutritionItem">
          <span>{ui.esc(tr(locale, "carbs"))}</span>
          <b>{n_carbs} g<br><small>{ui.esc(tr(locale, "sugars"))} {n_sug} g</small></b>
        </div>

        <div class="nutritionItem">
          <span>{ui.esc(tr(locale, "protein_salt"))}</span>
          <b>{n_prot} g / {n_salt} g</b>
        </div>
      </div>
    </section>

    <section class="infoCard full">
      <div class="cardHead">
        <div>
          <div class="cardTitle">{ui.esc(tr(locale, "recyclability"))}</div>
          <div class="cardSub">{ui.esc(tr(locale, "recycling_components"))}</div>
        </div>
        <div class="cardIcon">♻️</div>
      </div>

      <div class="recycleGrid">
        {recycle_html}
      </div>
    </section>
  </main>

  <div class="footerNote">
    {ui.esc(tr(locale, "digital_product_info"))}
  </div>
</div>
</body>
</html>"""

    return HTMLResponse(html)


@router.get("/e/{slug}", response_class=HTMLResponse)
def public_label(request: Request, slug: str):
    return _render_label_page(request, slug, preview=False)


@router.get("/preview/{slug}", response_class=HTMLResponse)
def preview_label(request: Request, slug: str):
    return _render_label_page(request, slug, preview=True)
