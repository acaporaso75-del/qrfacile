from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg
from qrfacile_app import ui

router = APIRouter()


@router.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request):
    user, conn = require_any_role(request, ["admin"])

    body = """
    <div class="card">
        <h1>Area Admin</h1>
        <p class="muted">Pannello amministratore QRFACILE</p>

        <div class="grid">
            <a class="card" href="/admin/credits">
                <h3>Gestione crediti</h3>
                <p class="muted">Visualizza e modifica crediti utenti</p>
            </a>
        </div>
    </div>
    """

    return ui.layout("Admin", body)


@router.get("/admin/credits", response_class=HTMLResponse)
def admin_credits(request: Request):
    user, conn = require_any_role(request, ["admin"])

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT u.id,
                   u.email,
                   u.role,
                   COALESCE(c.balance, 0) AS credits
            FROM users u
            LEFT JOIN user_credits c ON c.user_id = u.id
            ORDER BY u.id DESC
            LIMIT 200
        """)
        rows = cur.fetchall()

    table_rows = ""
    for r in rows:
        table_rows += f"""
        <tr>
            <td>{r["id"]}</td>
            <td>{r["email"]}</td>
            <td>{r["role"]}</td>
            <td>{r["credits"]}</td>
            <td>
                <form method="post" action="/admin/credits/apply" style="display:flex;gap:6px;">
                    <input type="hidden" name="user_id" value="{r["id"]}">
                    <input type="number" name="amount" placeholder="+/-" required>
                    <button type="submit">Applica</button>
                </form>
            </td>
        </tr>
        """

    body = f"""
    <div class="card">
        <h1>Gestione Crediti</h1>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Email</th>
                    <th>Ruolo</th>
                    <th>Crediti</th>
                    <th>Azione</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </div>
    """

    return ui.layout("Admin · Crediti", body)


@router.post("/admin/credits/apply")
def admin_apply_credits(request: Request):
    user, conn = require_any_role(request, ["admin"])

    form = request.form()
    user_id = int(form["user_id"])
    amount = int(form["amount"])

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO user_credits (user_id, balance)
            VALUES (%s, %s)
            ON CONFLICT (user_id)
            DO UPDATE SET balance = user_credits.balance + %s
        """, (user_id, amount, amount))

    conn.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse("/admin/credits", status_code=303)
