from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

from qrfacile_app.annual_packages import (
    anniversary, annual_quote, italian_vat_is_well_formed,
    load_order_product, validate_capture,
)
from qrfacile_app.pricing_config import list_qr_packs, get_purchase_pack, credit_cost_for_duration
from qrfacile_app.premium_ui import _subscription_gate_for_new_wine


@pytest.mark.parametrize("pack,units,net,gross", [
    ("annual_start", 15, 9900, 12078),
    ("annual_winery", 50, 17900, 21838),
    ("annual_business", 100, 29900, 36478),
])
def test_annual_catalogue_and_italian_quote(pack, units, net, gross):
    product = get_purchase_pack(pack)
    assert product["annual"] and not product["subscription"]
    assert product["wine_credits"] == units
    quote = annual_quote(pack, "IT", "IT12345678903")
    assert quote["net_cents"] == net
    assert quote["gross_cents"] == gross
    assert quote["vat_cents"] == gross-net
    assert quote["period_months"] == 12 and quote["renewal"] == "manual"
    assert quote["vat_number"] == "12345678903"
    assert "IVA esclusa" in product["price"]


def test_old_products_are_not_on_sale_but_original_entitlements_are_retained():
    assert {key for key, _ in list_qr_packs()} == {"annual_start", "annual_winery", "annual_business"}
    for key, units, amount in [("start",20,2900),("pro",60,7900),("plus",200,19900)]:
        product = load_order_product({"pack": key, "amount_cents": amount})
        assert product["disabled"] and product["wine_credits"] == units
        assert product["amount_cents"] == amount and not product["annual"]


@pytest.mark.parametrize("country,vat", [
    ("FR","12345678903"), ("IT",""), ("IT","123"), ("IT","abcdefghijk"),
    ("IT","12345678901"), ("IT","00000000000"), ("IT","11111111111"),
])
def test_unsupported_tax_details_fail_closed(country, vat):
    with pytest.raises(HTTPException):
        annual_quote("annual_start", country, vat)


def test_order_snapshot_not_current_catalogue_controls_fulfilment():
    quote = annual_quote("annual_start", "IT", "12345678903")
    quote["wine_credits"] = 17  # frozen, earlier offer
    order = {"pack": "annual_start", "amount_cents": 12078, "commercial_snapshot": quote}
    assert load_order_product(order)["wine_credits"] == 17
    order["amount_cents"] = 9900
    with pytest.raises(HTTPException):
        load_order_product(order)
    with pytest.raises(HTTPException):
        load_order_product({"pack":"annual_start"})


def test_anniversary_is_calendar_based_and_handles_leap_day():
    start = int(datetime(2024,2,29,12,tzinfo=timezone.utc).timestamp())
    assert datetime.fromtimestamp(anniversary(start),timezone.utc) == datetime(2025,2,28,12,tzinfo=timezone.utc)
    assert datetime.fromtimestamp(anniversary(start,25),timezone.utc) == datetime(2049,2,28,12,tzinfo=timezone.utc)
    assert credit_cost_for_duration(10) == 1
    assert credit_cost_for_duration(25) == 2


@pytest.mark.parametrize("value", ["12345678903", "IT12345678903", "IT 12345678903"])
def test_italian_vat_checksum_accepts_well_formed_numbers(value):
    assert italian_vat_is_well_formed(value)


def _capture():
    return {"id":"PP-TEST", "status":"COMPLETED", "purchase_units":[{
        "payments":{"captures":[{"id":"CAP-TEST","status":"COMPLETED","amount":{"value":"120.78","currency_code":"EUR"}}]}
    }]}


@pytest.mark.parametrize("fault", ["amount","currency","status","id","extra_unit","extra_capture","empty"])
def test_capture_mismatch_cannot_grant_units(fault):
    payload = _capture()
    capture = payload["purchase_units"][0]["payments"]["captures"][0]
    if fault == "amount": capture["amount"]["value"] = "99.00"
    if fault == "currency": capture["amount"]["currency_code"] = "USD"
    if fault == "status": capture["status"] = "PENDING"
    if fault == "id": payload["id"] = "OTHER"
    if fault == "extra_unit": payload["purchase_units"].append(deepcopy(payload["purchase_units"][0]))
    if fault == "extra_capture": payload["purchase_units"][0]["payments"]["captures"].append(deepcopy(capture))
    if fault == "empty": payload = {}
    with pytest.raises(RuntimeError):
        validate_capture(payload, {"paypal_order_id":"PP-TEST","amount_cents":12078,"currency":"EUR"})


def test_valid_capture():
    assert validate_capture(_capture(), {"paypal_order_id":"PP-TEST","amount_cents":12078,"currency":"EUR"}) == "CAP-TEST"


def test_rendered_pricing_discloses_annual_tax_and_duration_terms():
    from starlette.requests import Request
    from qrfacile_app.pricing_ui import pricing_page
    request = Request({"type":"http", "method":"GET", "path":"/pricing", "headers":[], "query_string":b""})
    html = " ".join(pricing_page(request).body.decode().split())
    for key in ("annual_start", "annual_winery", "annual_business"):
        assert f'name="pack" value="{key}"' in html
    for key in ("start", "pro", "plus"):
        assert f'name="pack" value="{key}"' not in html
    for text in (
        "120,78", "218,38", "364,78", "IVA esclusa",
        "Nessun abbonamento obbligatorio", "nessun rinnovo automatico",
        "anche senza nuovi acquisti", "/ pacchetto",
        "Un solo QR per tutta la produzione della referenza",
        "un lotto differente richiede un nuovo QR", "25 anni",
    ):
        assert text in html
    assert html.count('name="fiscal_confirmation"') == 3


def test_public_offer_leads_with_no_mandatory_subscription():
    from starlette.requests import Request
    from qrfacile_app.landing_routes import home, wine_home

    request = Request({"type":"http", "method":"GET", "path":"/", "headers":[], "query_string":b""})
    home_html = home(request).body.decode()
    wine_html = wine_home(request).body.decode()

    assert "Wine Compliance · senza canone annuale" in home_html
    assert "Nessun abbonamento obbligatorio" in wine_html
    assert "nessun rinnovo automatico" in wine_html
    assert "anche senza altri acquisti" in wine_html
    assert "tutte le bottiglie della medesima referenza" in wine_html
    assert "un lotto differente richiede un nuovo QR" in wine_html


def test_expired_legacy_subscription_does_not_block_available_units():
    class Cursor:
        def execute(self, sql, params):
            self.sql = sql
        def fetchone(self):
            return {"balance":15} if "available_credit_ledger" in self.sql else {"expires_at":1}
    assert _subscription_gate_for_new_wine(Cursor(), {"role":"winery"}, 42, 9) == (True,"")


def test_all_balance_reads_use_expiry_aware_view():
    import ast
    import re
    for path in (Path(__file__).resolve().parents[1]/"qrfacile_app").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not re.search(r"SUM\(delta\)[^;]*?FROM\s+credit_ledger", node.value, re.I), path
