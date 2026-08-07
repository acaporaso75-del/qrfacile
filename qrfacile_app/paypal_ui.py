# /opt/qrfacile/qrfacile_app/paypal_ui.py

import logging
import os
import time
import requests
from urllib.parse import quote_plus, urlsplit

from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from psycopg.rows import dict_row

from qrfacile_app.auth_core import require_any_role
from qrfacile_app.csrf_core import require_csrf
from qrfacile_app.db import pg

from qrfacile_app.pricing_config import (
    get_purchase_pack,
)

router = APIRouter()
logger = logging.getLogger("qrfacile.paypal")


PAYPAL_CLIENT_ID = (os.getenv("PAYPAL_CLIENT_ID") or "").strip()
PAYPAL_SECRET = (os.getenv("PAYPAL_SECRET") or "").strip()
PAYPAL_MODE = (os.getenv("PAYPAL_MODE") or "sandbox").strip().lower()

if PAYPAL_MODE not in {"sandbox", "live"}:
    raise RuntimeError("PAYPAL_MODE deve essere sandbox oppure live")

if PAYPAL_MODE == "live":
    PAYPAL_BASE = "https://api-m.paypal.com"
else:
    PAYPAL_BASE = "https://api-m.sandbox.paypal.com"


def now() -> int:
    return int(time.time())


def _base_url(request: Request) -> str:
    base = getattr(request.app.state, "app_base_url", "").rstrip("/")

    if base:
        return base

    host = request.headers.get("host", "localhost:8000")
    return f"{request.url.scheme}://{host}"


def _paypal_token() -> str:
    if not PAYPAL_CLIENT_ID or not PAYPAL_SECRET:
        raise HTTPException(
            500,
            "PayPal non configurato: mancano PAYPAL_CLIENT_ID / PAYPAL_SECRET",
        )

    try:
        r = requests.post(
            f"{PAYPAL_BASE}/v1/oauth2/token",
            auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise RuntimeError("Connessione PayPal non disponibile") from exc

    if r.status_code >= 400:
        raise HTTPException(
            500,
            "Autenticazione PayPal temporaneamente non disponibile",
        )

    try:
        data = r.json()
    except ValueError as exc:
        raise RuntimeError("Risposta PayPal non valida") from exc
    token = data.get("access_token")

    if not token:
        raise HTTPException(
            500,
            "PayPal non ha restituito access_token",
        )

    return token


def _approve_url(value: object) -> str:
    url = str(value or "").strip()
    parsed = urlsplit(url)
    expected_host = "www.paypal.com" if PAYPAL_MODE == "live" else "www.sandbox.paypal.com"
    if parsed.scheme != "https" or parsed.hostname != expected_host:
        raise RuntimeError("Link di approvazione PayPal non valido")
    return url


def _cancel_failed_order(order_id: int) -> None:
    try:
        with pg() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE orders SET status='cancelled' WHERE id=%s AND status='pending'",
                    (int(order_id),),
                )
                conn.commit()
    except Exception:
        logger.exception("Impossibile annullare l'ordine PayPal fallito %s", order_id)


def _checkout_error(order_id: int, exc: Exception) -> RedirectResponse:
    logger.warning("Checkout PayPal fallito per ordine %s: %s", order_id, type(exc).__name__)
    _cancel_failed_order(order_id)
    message = "PayPal non è temporaneamente raggiungibile. Riprova tra qualche minuto."
    return RedirectResponse(
        f"/app/billing?err={quote_plus(message)}",
        status_code=303,
    )


def _capture_error(order_id: int, exc: Exception) -> RedirectResponse:
    logger.warning("Conferma PayPal fallita per ordine %s: %s", order_id, type(exc).__name__)
    message = "Non è stato possibile confermare il pagamento. Nessun credito è stato caricato; riprova o contatta l'assistenza."
    return RedirectResponse(
        f"/app/billing?err={quote_plus(message)}",
        status_code=303,
    )


def _billing_winery_id(cur, user: dict) -> int | None:
    role = (user.get("role") or "").lower().strip()
    uid = int(user["id"])

    if role == "winery":
        cur.execute(
            """
            SELECT id
            FROM wineries
            WHERE owner_user_id=%s
            LIMIT 1
            """,
            (uid,),
        )

        r = cur.fetchone()

        return int(r["id"]) if r and r.get("id") else None

    if role == "admin":
        cur.execute(
            """
            SELECT admin_active_winery_id
            FROM users
            WHERE id=%s
            LIMIT 1
            """,
            (uid,),
        )

        r = cur.fetchone() or {}

        return (
            int(r["admin_active_winery_id"])
            if r.get("admin_active_winery_id")
            else None
        )

    return None


def _add_credit(
    cur,
    user_id: int,
    credit_type: str,
    delta: int,
    reason: str,
    ref_table: str,
    ref_id: int,
):
    if not delta:
        return

    cur.execute(
        """
        INSERT INTO credit_ledger (
          user_id,
          credit_type,
          delta,
          reason,
          ref_table,
          ref_id,
          created_at
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            int(user_id),
            credit_type,
            int(delta),
            reason,
            ref_table,
            int(ref_id),
            now(),
        ),
    )


@router.post("/paypal/start")
def paypal_start(
    request: Request,
    pack: str = Form(...),
    billing_winery_id: int = Form(0),
    csrf_token: str = Form(""),
):
    user = require_any_role(request, ("winery", "studio", "admin"))
    require_csrf(request, csrf_token)

    pack = (pack or "").strip().lower()

    data = get_purchase_pack(pack)

    if not data:
        raise HTTPException(400, "Pacchetto non valido")

    if data.get("disabled") or int(data.get("amount_cents") or 0) <= 0:
        raise HTTPException(400, "Pacchetto non acquistabile online")

    role = (user.get("role") or "").lower().strip()

    uid = int(user["id"])
    base = _base_url(request)

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            winery_id = _billing_winery_id(cur, user)

            # Studio: crediti caricati sullo studio
            if role == "studio":
                winery_id = None

            # Admin può scegliere cantina target
            if role == "admin" and int(billing_winery_id or 0):

                cur.execute(
                    """
                    SELECT id
                    FROM wineries
                    WHERE id=%s
                    LIMIT 1
                    """,
                    (int(billing_winery_id),),
                )

                if not cur.fetchone():
                    raise HTTPException(404, "Cantina non trovata")

                winery_id = int(billing_winery_id)

            cur.execute(
                """
                INSERT INTO orders (
                  user_id,
                  billing_winery_id,
                  pack,
                  qty,
                  amount_cents,
                  currency,
                  status,
                  created_at
                )
                VALUES (%s,%s,%s,1,%s,'EUR','pending',%s)
                RETURNING id
                """,
                (
                    uid,
                    winery_id,
                    pack,
                    int(data["amount_cents"]),
                    now(),
                ),
            )

            order_id = int(cur.fetchone()["id"])

            conn.commit()

    try:
        token = _paypal_token()
        return_url = f"{base}/paypal/return?order_id={order_id}"
        cancel_url = f"{base}/app/billing?err=Pagamento%20annullato"
        r = requests.post(
            f"{PAYPAL_BASE}/v2/checkout/orders",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": f"qrfacile-order-{order_id}",
            },
            json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": str(order_id),
                    "custom_id": str(order_id),
                    "description": f"QRFACILE crediti/servizio {data['name']}",
                    "amount": {
                        "currency_code": "EUR",
                        "value": f"{int(data['amount_cents']) / 100:.2f}",
                    },
                }],
                "application_context": {
                    "brand_name": "QRFACILE",
                    "landing_page": "LOGIN",
                    "user_action": "PAY_NOW",
                    "return_url": return_url,
                    "cancel_url": cancel_url,
                },
            },
            timeout=30,
        )
        if r.status_code >= 400:
            raise RuntimeError("Creazione ordine PayPal non disponibile")
        pp = r.json()
        if not isinstance(pp, dict):
            raise RuntimeError("Risposta ordine PayPal non valida")
        paypal_id = str(pp.get("id") or "").strip()
        if not paypal_id:
            raise RuntimeError("PayPal non ha restituito un ordine valido")
        links = pp.get("links") or []
        if not isinstance(links, list):
            raise RuntimeError("Link ordine PayPal non validi")
        approve_link = next(
            (link.get("href") for link in links if isinstance(link, dict) and link.get("rel") == "approve"),
            "",
        )
        approve_url = _approve_url(approve_link)
    except (HTTPException, RuntimeError, requests.RequestException, ValueError) as exc:
        return _checkout_error(order_id, exc)

    try:
        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE orders
                    SET paypal_order_id=%s
                    WHERE id=%s
                    """,
                    (paypal_id, int(order_id)),
                )
                conn.commit()
    except Exception as exc:
        return _checkout_error(order_id, exc)

    return RedirectResponse(
        approve_url,
        status_code=303,
    )


@router.get("/paypal/return")
def paypal_return(
    request: Request,
    token: str = "",
    order_id: int = 0,
):
    """
    PayPal ritorna con token = PayPal order id.
    order_id è il nostro id interno passato nella return_url.
    """

    user = require_any_role(request, ("winery", "studio", "admin"))

    uid = int(user["id"])

    paypal_order_id = (token or "").strip()

    if not paypal_order_id:
        raise HTTPException(400, "Token PayPal mancante")

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            if order_id:

                cur.execute(
                    """
                    SELECT *
                    FROM orders
                    WHERE id=%s
                      AND user_id=%s
                    LIMIT 1
                    """,
                    (int(order_id), uid),
                )

            else:

                cur.execute(
                    """
                    SELECT *
                    FROM orders
                    WHERE paypal_order_id=%s
                      AND user_id=%s
                    LIMIT 1
                    """,
                    (paypal_order_id, uid),
                )

            order = cur.fetchone()

            if not order:
                raise HTTPException(404, "Ordine non trovato")

            saved_paypal_order_id = (order.get("paypal_order_id") or "").strip()
            if not saved_paypal_order_id:
                raise HTTPException(400, "Ordine PayPal non coerente")
            if saved_paypal_order_id != paypal_order_id:
                raise HTTPException(400, "Ordine PayPal non coerente")

            if (order.get("status") or "").lower() == "paid":

                return RedirectResponse(
                    "/app/billing?msg=Pagamento%20già%20registrato",
                    status_code=303,
                )

    try:
        token_api = _paypal_token()
        r = requests.post(
            f"{PAYPAL_BASE}/v2/checkout/orders/{paypal_order_id}/capture",
            headers={
                "Authorization": f"Bearer {token_api}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": f"qrfacile-capture-{int(order['id'])}",
            },
            timeout=30,
        )
        if r.status_code >= 400:
            raise RuntimeError("Capture PayPal non disponibile")
        capture_data = r.json()
        if not isinstance(capture_data, dict):
            raise RuntimeError("Risposta capture PayPal non valida")
        status = str(capture_data.get("status") or "").upper()
        if status != "COMPLETED":
            raise RuntimeError("Pagamento PayPal non completato")
    except (HTTPException, RuntimeError, requests.RequestException, ValueError) as exc:
        return _capture_error(int(order["id"]), exc)

    capture_id = ""

    try:
        captures = capture_data["purchase_units"][0]["payments"]["captures"]

        if captures:
            capture_id = captures[0].get("id") or ""

    except Exception:
        capture_id = ""

    with pg() as conn:
        with conn.cursor(row_factory=dict_row) as cur:

            cur.execute(
                """
                SELECT *
                FROM orders
                WHERE id=%s
                  AND user_id=%s
                FOR UPDATE
                """,
                (int(order["id"]), uid),
            )

            locked_order = cur.fetchone()

            if not locked_order:
                raise HTTPException(404, "Ordine non trovato")

            locked_paypal_order_id = (locked_order.get("paypal_order_id") or "").strip()
            if not locked_paypal_order_id:
                raise HTTPException(400, "Ordine PayPal non coerente")
            if locked_paypal_order_id != paypal_order_id:
                raise HTTPException(400, "Ordine PayPal non coerente")

            if (locked_order.get("status") or "").lower() == "paid":

                conn.commit()

                return RedirectResponse(
                    "/app/billing?msg=Pagamento%20già%20registrato",
                    status_code=303,
                )

            pack = (locked_order.get("pack") or "").strip().lower()

            data = get_purchase_pack(pack)

            if not data:
                raise HTTPException(
                    400,
                    "Pacchetto ordine non valido",
                )

            order_id_int = int(locked_order["id"])

            cur.execute(
                """
                UPDATE orders
                SET status='paid',
                    paypal_order_id=%s,
                    paypal_capture_id=%s,
                    paid_at=%s
                WHERE id=%s
                """,
                (
                    paypal_order_id,
                    capture_id,
                    now(),
                    order_id_int,
                ),
            )

            # wine credits
            if int(data.get("wine_credits") or 0):

                _add_credit(
                    cur,
                    uid,
                    "wine",
                    int(data["wine_credits"]),
                    "purchase",
                    "orders",
                    order_id_int,
                )

            # generic credits
            if int(data.get("generic_credits") or 0):

                _add_credit(
                    cur,
                    uid,
                    "generic",
                    int(data["generic_credits"]),
                    "purchase",
                    "orders",
                    order_id_int,
                )

            conn.commit()

    return RedirectResponse(
        "/app/billing?msg=Pagamento%20completato%2C%20crediti%20caricati",
        status_code=303,
    )


@router.get("/paypal/debug", response_class=HTMLResponse)
def paypal_debug(request: Request):
    require_any_role(request, ("admin",))

    mode = PAYPAL_MODE
    configured = bool(PAYPAL_CLIENT_ID and PAYPAL_SECRET)

    return HTMLResponse(
        f"""
        <h1>PayPal debug</h1>
        <p>Mode: <b>{mode}</b></p>
        <p>Base: <b>{PAYPAL_BASE}</b></p>
        <p>Configured: <b>{configured}</b></p>
        """
    )

