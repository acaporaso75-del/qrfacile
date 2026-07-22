import time
from typing import Set

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
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


def _cols(cur, table: str) -> Set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        """,
        (table,),
    )
    return {r["column_name"] for r in (cur.fetchall() or [])}


def _load_label(cur, label_id: int) -> dict:
    cur.execute("""
      SELECT
        wl.id AS label_id,
        wl.winery_id,
        wl.wine_id,
        wl.label_type,
        wl.language,
        wl.updated_at,
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


@router.get("/app/label/{label_id}/compliance", response_class=HTMLResponse)
def label_compliance_page(request: Request, label_id: int):
    user = require_any_role(request, ("winery", "studio", "admin"))
    role = (user.get("role") or "").lower().strip()

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            label = _load_label(cur, int(label_id))
            if not _can_view(user, label, cur):
                raise HTTPException(403, "Forbidden")

            # ------------ nutrition ------------
            nut = {}
            try:
                ncols = _cols(cur, "label_nutrition")
                if "label_id" in ncols:
                    fields = [f for f in [
                        "energy_kj", "energy_kcal", "fat", "saturates", "carbs", "sugars", "protein", "salt", "updated_at"
                    ] if f in ncols]
                    if fields:
                        cur.execute(
                            f"SELECT {', '.join(fields)} FROM label_nutrition WHERE label_id=%s LIMIT 1",
                            (int(label_id),),
                        )
                        nut = cur.fetchone() or {}
            except Exception:
                nut = {}

            # ------------ ingredients (NO custom_text) ------------
            ingredients = []
            try:
                icols = _cols(cur, "label_ingredients")
                if "label_id" in icols and "ingredient_id" in icols:
                    cur.execute("""
                      SELECT im.name AS name
                      FROM label_ingredients li
                      JOIN ingredients_master im ON im.id = li.ingredient_id
                      WHERE li.label_id=%s
                      ORDER BY im.name
                      LIMIT 400
                    """, (int(label_id),))
                    ingredients = [r["name"] for r in (cur.fetchall() or []) if r.get("name")]
            except Exception:
                ingredients = []

            # ------------ allergens (try custom_text only if exists) ------------
            allergens = []
            try:
                acols = _cols(cur, "label_allergens")
                if "label_id" in acols:
                    has_custom = "custom_text" in acols
                    has_id = "allergen_id" in acols
                    if has_id and has_custom:
                        cur.execute("""
                          SELECT COALESCE(am.name, la.custom_text) AS name
                          FROM label_allergens la
                          LEFT JOIN allergens_master am ON am.id = la.allergen_id
                          WHERE la.label_id=%s
                          ORDER BY am.name NULLS LAST, la.custom_text NULLS LAST
                          LIMIT 300
                        """, (int(label_id),))
                    elif has_id:
                        cur.execute("""
                          SELECT am.name AS name
                          FROM label_allergens la
                          JOIN allergens_master am ON am.id = la.allergen_id
                          WHERE la.label_id=%s
                          ORDER BY am.name
                          LIMIT 300
                        """, (int(label_id),))
                    elif has_custom:
                        cur.execute("""
                          SELECT la.custom_text AS name
                          FROM label_allergens la
                          WHERE la.label_id=%s
                          ORDER BY la.custom_text
                          LIMIT 300
                        """, (int(label_id),))
                    else:
                        cur.execute("SELECT NULL AS name WHERE 1=0")
                    allergens = [r["name"] for r in (cur.fetchall() or []) if r.get("name")]
            except Exception:
                allergens = []

            # ------------ recycle (label_recycle_items) ------------
            recycle = []
            try:
                rcols = _cols(cur, "label_recycle_items")
                if "label_id" in rcols:
                    fields = [f for f in ["component", "product", "code", "extra_code", "note", "updated_at"] if f in rcols]
                    if not fields:
                        fields = ["component", "code"]
                    cur.execute(
                        f"SELECT {', '.join(fields)} FROM label_recycle_items WHERE label_id=%s ORDER BY component LIMIT 80",
                        (int(label_id),),
                    )
                    recycle = cur.fetchall() or []
            except Exception:
                recycle = []

    def cell(v) -> str:
        return ui.esc("" if v is None else str(v))

    winery_name = label.get("winery_name") or "-"
    wine_name = label.get("wine_name") or "-"
    lt = (label.get("label_type") or "").strip()
    lang = (label.get("language") or "").strip()
    upd = _fmt_ts(int(label.get("updated_at") or 0))

    ing_html = ", ".join(ui.esc(x) for x in ingredients) if ingredients else "<span class='muted'>Nessun ingrediente</span>"
    all_html = ", ".join(ui.esc(x) for x in allergens) if allergens else "<span class='muted'>Nessun allergene</span>"

    rec_rows = ""
    for r in recycle:
        rec_rows += f"""
        <tr>
          <td>{cell(r.get("component"))}</td>
          <td>{cell(r.get("product"))}</td>
          <td><b>{cell(r.get("code"))}</b></td>
          <td>{cell(r.get("extra_code"))}</td>
          <td>{cell(r.get("note"))}</td>
        </tr>
        """
    if not rec_rows:
        rec_rows = "<tr><td colspan='5' class='muted'>Nessun dato riciclo</td></tr>"

    html_out = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Compliance etichetta #{int(label_id)}</title>
<link rel="stylesheet" href="/static/app.css">
<style>
table{{width:100%;border-collapse:separate;border-spacing:0 10px}}
th{{text-align:left;color:var(--muted);font-size:12px}}
td{{background:rgba(255,255,255,.92);border:1px solid var(--line);padding:10px;border-left:none}}
td:first-child{{border-left:1px solid var(--line);border-top-left-radius:12px;border-bottom-left-radius:12px}}
td:last-child{{border-top-right-radius:12px;border-bottom-right-radius:12px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}
@media (max-width:900px){{.grid{{grid-template-columns:repeat(2,1fr)}}}}
</style>
</head>
<body>
<div class="container">

  <div class="topbar">
    <div class="brand">
      <div class="brand-dot"></div>
      <div>
        <div class="brand-title">QRFACILE</div>
        <div class="brand-sub">Etichetta · Compliance</div>
      </div>
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <a class="pill" href="/app/label/{int(label_id)}">← Etichetta</a>
      <a class="pill" href="/app/labels/search">Ricerca avanzata</a>
      <a class="pill" href="/logout">Logout</a>
    </div>
  </div>

  <div class="h1">Compliance etichetta #{int(label_id)}</div>
  <div class="p">{ui.esc(winery_name)} · {ui.esc(wine_name)} · tipo {ui.esc(lt)} · lang {ui.esc(lang)} · agg. {ui.esc(upd)}</div>

  <div class="card" style="margin-top:14px">
    <div class="section-title">Valori nutrizionali (label)</div>
    <div class="grid" style="margin-top:10px">
      <div class="card"><b>Energia</b><div class="muted">{cell(nut.get("energy_kj"))} kJ / {cell(nut.get("energy_kcal"))} kcal</div></div>
      <div class="card"><b>Grassi</b><div class="muted">{cell(nut.get("fat"))} g</div></div>
      <div class="card"><b>Saturi</b><div class="muted">{cell(nut.get("saturates"))} g</div></div>
      <div class="card"><b>Carboidrati</b><div class="muted">{cell(nut.get("carbs"))} g</div></div>
      <div class="card"><b>Zuccheri</b><div class="muted">{cell(nut.get("sugars"))} g</div></div>
      <div class="card"><b>Proteine</b><div class="muted">{cell(nut.get("protein"))} g</div></div>
      <div class="card"><b>Sale</b><div class="muted">{cell(nut.get("salt"))} g</div></div>
      <div class="card"><b>Aggiornato</b><div class="muted">{cell(_fmt_ts(int(nut.get("updated_at") or 0)))}</div></div>
    </div>
  </div>

  <div class="card" style="margin-top:14px">
    <div class="section-title">Ingredienti</div>
    <div class="p">{ing_html}</div>
  </div>

  <div class="card" style="margin-top:14px">
    <div class="section-title">Allergeni</div>
    <div class="p">{all_html}</div>
  </div>

  <div class="card" style="margin-top:14px">
    <div class="section-title">Riciclabilità (label)</div>
    <table>
      <thead>
        <tr>
          <th>Componente</th><th>Prodotto</th><th>Codice</th><th>Extra</th><th>Note</th>
        </tr>
      </thead>
      <tbody>
        {rec_rows}
      </tbody>
    </table>
  </div>

</div>
</body>
</html>
"""
    return HTMLResponse(html_out)
