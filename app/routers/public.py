import csv, io, secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.db.conn import db
from qrfacile_app.services.storage import get_templates_dir

router = APIRouter()

templates = Environment(
    loader=FileSystemLoader(str(get_templates_dir())),
    autoescape=select_autoescape(["html"])
)

def now_epoch() -> int:
    return int(datetime.now(timezone.utc).timestamp())

def new_slug(n=8):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # pragma: allowlist secret
    return "".join(secrets.choice(alphabet) for _ in range(n))

def get_default_user_id(cur) -> int:
    cur.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1")
    u = cur.fetchone()
    return int(u["id"]) if u else 1

@router.get("/", response_class=HTMLResponse)
def admin_home():
    tpl = templates.get_template("admin_home.html")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT id, slug, title, qr_type, status, winery_id, year, lot, created_at
              FROM qr_items
              ORDER BY id DESC
              LIMIT 200
            """)
            rows = cur.fetchall()
    return HTMLResponse(tpl.render(rows=rows))

@router.post("/create-url")
def create_url_qr(
    title: str = Form(...),
    url: str = Form(...),
    winery_id: int = Form(0)
):
    created_at = now_epoch()
    slug = new_slug()

    payload = {"kind": "url", "url": url}

    with db() as conn:
        with conn.cursor() as cur:
            owner_user_id = get_default_user_id(cur)

            cur.execute("""
              INSERT INTO qr_items(
                owner_user_id, winery_id, qr_type, status, slug, title,
                payload, created_at, updated_at
              )
              VALUES (%s, NULLIF(%s,0), %s, %s, %s, %s, %s::jsonb, %s, %s)
              RETURNING id
            """, (owner_user_id, winery_id, "url", "active", slug, title, io.StringIO(str(payload)).getvalue().replace("'", '"'), created_at, created_at))
            qr_id = cur.fetchone()["id"]

            # snapshot storico
            cur.execute("""
              INSERT INTO qr_history(qr_id, snapshot, created_at, actor_user_id)
              VALUES (%s, %s::jsonb, %s, %s)
            """, (qr_id, io.StringIO(str(payload)).getvalue().replace("'", '"'), created_at, owner_user_id))

            conn.commit()

    return RedirectResponse("/admin", status_code=303)

@router.post("/create-wine")
def create_wine_qr(
    title: str = Form(...),
    winery_id: int = Form(...),
    year: str = Form(""),
    lot: str = Form("")
):
    created_at = now_epoch()
    slug = new_slug()

    # payload base (poi lo completiamo in editor)
    payload = {
        "kind": "wine",
        "wine_name": title,
        "ingredients": "",
        "allergens": "",
        "nutrition": {
            "energy": "",
            "carbs": "",
            "sugars": "",
            "fat": "",
            "protein": "",
            "salt": ""
        },
        "recycling": []
    }

    with db() as conn:
        with conn.cursor() as cur:
            owner_user_id = get_default_user_id(cur)

            # cache nome cantina
            cur.execute("SELECT name FROM wineries WHERE id=%s", (winery_id,))
            w = cur.fetchone()
            winery_name_cache = (w["name"] if w else "")

            payload["winery_name"] = winery_name_cache

            # jsonb safe: passiamo come stringa json
            import json
            payload_json = json.dumps(payload, ensure_ascii=False)

            cur.execute("""
              INSERT INTO qr_items(
                owner_user_id, winery_id, qr_type, status, slug, title,
                year, lot, winery_name_cache,
                payload, created_at, updated_at
              )
              VALUES (%s, %s, %s, %s, %s, %s, NULLIF(%s,''), NULLIF(%s,''), %s, %s::jsonb, %s, %s)
              RETURNING id
            """, (owner_user_id, winery_id, "wine", "active", slug, title, year, lot, winery_name_cache, payload_json, created_at, created_at))
            qr_id = cur.fetchone()["id"]

            cur.execute("""
              INSERT INTO qr_history(qr_id, snapshot, created_at, actor_user_id)
              VALUES (%s, %s::jsonb, %s, %s)
            """, (qr_id, payload_json, created_at, owner_user_id))

            conn.commit()

    return RedirectResponse("/admin", status_code=303)

@router.get("/export-scans-daily.csv")
def export_scans_daily():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT day, slug, scans
              FROM qr_scans_daily
              ORDER BY day DESC, scans DESC
              LIMIT 50000
            """)
            rows = cur.fetchall()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["day","slug","scans"])
    for r in rows:
        w.writerow([r["day"], r["slug"], r["scans"]])

    out = io.BytesIO(buf.getvalue().encode("utf-8"))
    return StreamingResponse(out, media_type="text/csv",
                            headers={"Content-Disposition":"attachment; filename=scans_daily.csv"})
