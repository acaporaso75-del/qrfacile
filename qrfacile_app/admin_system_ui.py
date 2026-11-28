import platform
import shutil
import subprocess
import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.db import pg


router = APIRouter(prefix="/admin", tags=["admin-system"])

START_TIME = time.time()
APP_ROOT = "/opt/qrfacile-staging"


def get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=APP_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).strip()
    except Exception:
        return "unknown"


def format_uptime(seconds: int) -> str:
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []

    if days:
        parts.append(f"{days}g")

    if hours or days:
        parts.append(f"{hours}h")

    if minutes or hours or days:
        parts.append(f"{minutes}m")

    parts.append(f"{seconds}s")

    return " ".join(parts)


def status_badge(status: str) -> str:
    if status == "OK":
        return """
        <span style="
            display:inline-block;
            padding:5px 10px;
            border-radius:999px;
            background:#dcfce7;
            color:#166534;
            font-weight:700;
        ">OK</span>
        """

    return """
    <span style="
        display:inline-block;
        padding:5px 10px;
        border-radius:999px;
        background:#fee2e2;
        color:#991b1b;
        font-weight:700;
    ">ERROR</span>
    """


@router.get("/system", response_class=HTMLResponse)
def admin_system(request: Request):
    user = require_any_role(request, ("admin",))

    database_status = "OK"
    database_name = "-"
    database_user = "-"
    database_latency_ms = "-"

    try:
        started = time.perf_counter()

        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        current_database() AS database_name,
                        current_user AS database_user
                    """
                )
                row = cur.fetchone() or {}

        elapsed = (time.perf_counter() - started) * 1000

        database_name = row.get("database_name") or "-"
        database_user = row.get("database_user") or "-"
        database_latency_ms = f"{elapsed:.2f} ms"

    except Exception:
        database_status = "ERROR"

    disk = shutil.disk_usage("/")
    uptime_seconds = int(time.time() - START_TIME)

    disk_total_gb = disk.total / (1024 ** 3)
    disk_used_gb = disk.used / (1024 ** 3)
    disk_free_gb = disk.free / (1024 ** 3)
    disk_used_percent = (disk.used / disk.total) * 100 if disk.total else 0

    admin_name = (
        user.get("name")
        or user.get("email")
        or user.get("username")
        or f"Utente {user.get('id', '-')}"
    )

    html = f"""
<!doctype html>
<html lang="it">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>QRFacile · Stato sistema</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            padding: 32px;
            background: #f4f6f8;
            color: #172033;
            font-family: Arial, Helvetica, sans-serif;
        }}

        .container {{
            max-width: 1100px;
            margin: 0 auto;
        }}

        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
            margin-bottom: 24px;
        }}

        h1 {{
            margin: 0;
            font-size: 30px;
        }}

        .subtitle {{
            margin-top: 7px;
            color: #667085;
        }}

        .actions {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .btn {{
            display: inline-block;
            padding: 10px 15px;
            border-radius: 8px;
            background: white;
            color: #172033;
            border: 1px solid #d0d5dd;
            text-decoration: none;
            font-weight: 600;
        }}

        .btn-primary {{
            background: #172033;
            color: white;
            border-color: #172033;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(245px, 1fr));
            gap: 16px;
        }}

        .card {{
            background: white;
            border: 1px solid #e4e7ec;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04);
        }}

        .card-title {{
            color: #667085;
            font-size: 14px;
            margin-bottom: 10px;
        }}

        .card-value {{
            font-size: 21px;
            font-weight: 700;
            overflow-wrap: anywhere;
        }}

        .section {{
            margin-top: 22px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th,
        td {{
            text-align: left;
            padding: 13px 12px;
            border-bottom: 1px solid #eaecf0;
            vertical-align: top;
        }}

        th {{
            width: 32%;
            color: #667085;
            font-weight: 600;
        }}

        tr:last-child th,
        tr:last-child td {{
            border-bottom: 0;
        }}

        .progress {{
            height: 10px;
            margin-top: 12px;
            background: #eaecf0;
            border-radius: 999px;
            overflow: hidden;
        }}

        .progress-bar {{
            height: 100%;
            width: {disk_used_percent:.1f}%;
            background: #344054;
        }}

        .note {{
            margin-top: 22px;
            color: #667085;
            font-size: 13px;
        }}

        @media (max-width: 700px) {{
            body {{
                padding: 18px;
            }}

            .header {{
                align-items: flex-start;
                flex-direction: column;
            }}

            th {{
                width: 42%;
            }}
        }}
    </style>
</head>

<body>
    <div class="container">

        <div class="header">
            <div>
                <h1>Stato sistema QRFacile</h1>
                <div class="subtitle">
                    Ambiente staging · Accesso: {admin_name}
                </div>
            </div>

            <div class="actions">
                <a class="btn" href="/admin">Amministrazione</a>
                <a class="btn" href="/app/start">Menu</a>
                <a class="btn btn-primary" href="/admin/system">Aggiorna</a>
            </div>
        </div>

        <div class="grid">

            <div class="card">
                <div class="card-title">Applicazione</div>
                <div class="card-value">{status_badge("OK")}</div>
            </div>

            <div class="card">
                <div class="card-title">Database PostgreSQL</div>
                <div class="card-value">{status_badge(database_status)}</div>
            </div>

            <div class="card">
                <div class="card-title">Versione Git</div>
                <div class="card-value">{get_git_commit()}</div>
            </div>

            <div class="card">
                <div class="card-title">Uptime applicazione</div>
                <div class="card-value">{format_uptime(uptime_seconds)}</div>
            </div>

        </div>

        <div class="section card">
            <div class="card-title">Database</div>

            <table>
                <tr>
                    <th>Stato</th>
                    <td>{status_badge(database_status)}</td>
                </tr>
                <tr>
                    <th>Nome database</th>
                    <td>{database_name}</td>
                </tr>
                <tr>
                    <th>Utente database</th>
                    <td>{database_user}</td>
                </tr>
                <tr>
                    <th>Tempo di risposta</th>
                    <td>{database_latency_ms}</td>
                </tr>
            </table>
        </div>

        <div class="section card">
            <div class="card-title">Server</div>

            <table>
                <tr>
                    <th>Hostname</th>
                    <td>{platform.node()}</td>
                </tr>
                <tr>
                    <th>Sistema operativo</th>
                    <td>{platform.platform()}</td>
                </tr>
                <tr>
                    <th>Versione Python</th>
                    <td>{platform.python_version()}</td>
                </tr>
                <tr>
                    <th>Architettura</th>
                    <td>{platform.machine()}</td>
                </tr>
                <tr>
                    <th>Directory applicazione</th>
                    <td>{APP_ROOT}</td>
                </tr>
            </table>
        </div>

        <div class="section card">
            <div class="card-title">Spazio disco</div>

            <table>
                <tr>
                    <th>Totale</th>
                    <td>{disk_total_gb:.2f} GB</td>
                </tr>
                <tr>
                    <th>Utilizzato</th>
                    <td>{disk_used_gb:.2f} GB</td>
                </tr>
                <tr>
                    <th>Disponibile</th>
                    <td>{disk_free_gb:.2f} GB</td>
                </tr>
                <tr>
                    <th>Percentuale utilizzata</th>
                    <td>{disk_used_percent:.1f}%</td>
                </tr>
            </table>

            <div class="progress">
                <div class="progress-bar"></div>
            </div>
        </div>

        <div class="note">
            Pagina riservata agli utenti con ruolo amministratore.
        </div>

    </div>
</body>
</html>
"""

    return HTMLResponse(content=html, status_code=200)
