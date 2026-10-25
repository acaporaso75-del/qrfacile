"""Annual creation allowance; never controls the lifetime of existing labels."""
from calendar import monthrange
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException

from qrfacile_app.pricing_config import get_purchase_pack


def italian_vat_is_well_formed(value: str) -> bool:
    digits = "".join((value or "").strip().upper().removeprefix("IT").split())
    if len(digits) != 11 or not digits.isdigit() or len(set(digits)) == 1:
        return False
    total = sum(int(digits[index]) for index in range(0, 10, 2))
    for index in range(1, 10, 2):
        doubled = int(digits[index]) * 2
        total += doubled - 9 if doubled > 9 else doubled
    return (10 - total % 10) % 10 == int(digits[-1])


def anniversary(timestamp: int, years: int = 1) -> int:
    start = datetime.fromtimestamp(timestamp, timezone.utc)
    year = start.year + years
    return int(start.replace(year=year, day=min(start.day, monthrange(year, start.month)[1])).timestamp())


def annual_quote(pack: str, country: str, vat: str) -> dict:
    data = get_purchase_pack(pack)
    if not data or not data.get('annual'):
        raise HTTPException(400, 'Pacchetto annuale non valido')
    # Foreign/special fiscal cases need a reviewed quote, not a guessed exemption.
    normalized_vat = "".join(vat.strip().upper().removeprefix('IT').split())
    if country.strip().upper() != 'IT' or not italian_vat_is_well_formed(normalized_vat):
        raise HTTPException(422, 'Dati fiscali da verificare: richiedi un preventivo per il tuo paese o regime IVA.')
    net = int(data['amount_cents'])
    tax = int((Decimal(net) * Decimal('0.22')).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    return {
        'version': 'wine-annual-2026-10-25', 'pack': pack, 'name': data['name'],
        'annual': True, 'wine_credits': data['wine_credits'], 'generic_credits': 0,
        'net_cents': net, 'vat_cents': tax, 'vat_rate': '22',
        'gross_cents': net + tax, 'currency': 'EUR', 'billing_country': 'IT',
        'vat_number': normalized_vat,
        'renewal': 'manual', 'period_months': 12,
    }


def load_order_product(order: dict) -> dict:
    snapshot = order.get('commercial_snapshot')
    if snapshot:
        if snapshot.get('pack') != order.get('pack') or snapshot.get('gross_cents') != int(order['amount_cents']):
            raise HTTPException(409, 'Condizioni ordine incoerenti')
        return snapshot
    data = get_purchase_pack(order.get('pack') or '')
    if not data or data.get('annual'):
        raise HTTPException(409, 'Condizioni ordine mancanti')
    return data


def grant_annual_units(cur, *, user_id: int, order_id: int, units: int, paid_at: int):
    cur.execute(
        """INSERT INTO credit_ledger
        (user_id, credit_type, delta, reason, ref_table, ref_id, created_at, expires_at)
        VALUES (%s, 'wine', %s, 'annual_purchase', 'orders', %s, %s, %s)""",
        (user_id, units, order_id, paid_at, anniversary(paid_at)),
    )


def validate_capture(payload: dict, order: dict) -> str:
    try:
        if len(payload['purchase_units']) != 1:
            raise ValueError('purchase unit count')
        captures = payload['purchase_units'][0]['payments']['captures']
        if len(captures) != 1:
            raise ValueError('capture count')
        capture = captures[0]
        if not isinstance(capture, dict):
            raise ValueError('invalid capture')
        expected = Decimal(int(order['amount_cents'])) / 100
        if (payload.get('id') != order['paypal_order_id']
            or payload.get('status') != 'COMPLETED'
            or capture.get('status') != 'COMPLETED'
            or capture['amount']['currency_code'] != order['currency']
            or Decimal(capture['amount']['value']) != expected
            or not capture.get('id')):
            raise ValueError('capture mismatch')
        return str(capture['id'])
    except (KeyError, IndexError, TypeError, ValueError, ArithmeticError) as exc:
        raise RuntimeError('Importo o valuta PayPal non coerente con ordine') from exc
