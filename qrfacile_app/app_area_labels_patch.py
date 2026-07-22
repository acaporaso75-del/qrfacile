from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg

router = APIRouter()

@router.get("/app/labels", response_class=HTMLResponse)
def labels_menu(request: Request):
    user, conn = require_any_role(request, ["winery", "studio", "admin"])
    conn.close()
    return HTMLResponse("""
<h2>Etichette</h2>
<p><a href="/app/labels/search">Ricerca etichette (filtri + stampa + export ZIP)</a></p>
<p><a href="/app">Dashboard</a></p>
""")

