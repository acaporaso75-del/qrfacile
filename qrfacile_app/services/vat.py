"""VAT quote for QRFacile Link: price is VAT included, integer cents only.

Categories:
- it: Italian customer (company, private, association): Italian 22%.
- eu_consumer: EU customer without a VIES-valid VAT number: Italian 22%
  under the EU OSS threshold, destination rate once it is exceeded.
- eu_business_reverse_charge: EU business with VIES-valid VAT number: the
  net price, no VAT (reverse charge).
- extra_eu: outside the EU: the net price, out of scope of Italian VAT.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException

from qrfacile_app.pricing_config import EU_VAT_RATES, FOREIGN_VAT_CODES

ITALIAN_RATE = "22"


def _net(gross_cents: int, rate: str) -> int:
    value = Decimal(int(gross_cents)) * 100 / (100 + Decimal(rate))
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _italian_code() -> dict:
    return {"perc": 22, "class": "Imponibile", "description": "IVA 22%", "note": ""}


def link_quote(*, profile: dict, gross_cents: int = 2900, oss_threshold_exceeded: bool, foreign_enabled: bool) -> dict:
    country = str(profile.get("country") or "").upper()
    italian_net = _net(gross_cents, ITALIAN_RATE)
    if country == "IT":
        return {
            "category": "it", "vat_rate": ITALIAN_RATE, "net_cents": italian_net,
            "vat_cents": gross_cents - italian_net, "gross_cents": gross_cents,
            "vat_code": _italian_code(), "exemption_note": "",
        }
    if not foreign_enabled:
        raise HTTPException(422, "Gli acquisti dall'estero non sono ancora attivi. Scrivici a info@qrfacile.it.")
    if country in EU_VAT_RATES:
        is_business = profile.get("customer_type") == "company" and bool(profile.get("vat_number"))
        if is_business:
            if profile.get("vies_valid") is not True:
                raise HTTPException(422, "Partita IVA UE non verificata su VIES: controlla il numero o riprova più tardi.")
            code = FOREIGN_VAT_CODES["eu_reverse_charge"]
            return {
                "category": "eu_business_reverse_charge", "vat_rate": "0", "net_cents": italian_net,
                "vat_cents": 0, "gross_cents": italian_net, "vat_code": code, "exemption_note": code["note"],
            }
        if oss_threshold_exceeded:
            rate = EU_VAT_RATES[country]
            net = _net(gross_cents, rate)
            code = FOREIGN_VAT_CODES["eu_consumer_oss"]
            return {
                "category": "eu_consumer", "vat_rate": rate, "net_cents": net,
                "vat_cents": gross_cents - net, "gross_cents": gross_cents,
                "vat_code": code, "exemption_note": code["note"],
            }
        return {
            "category": "eu_consumer", "vat_rate": ITALIAN_RATE, "net_cents": italian_net,
            "vat_cents": gross_cents - italian_net, "gross_cents": gross_cents,
            "vat_code": _italian_code(), "exemption_note": "",
        }
    code = FOREIGN_VAT_CODES["extra_eu"]
    return {
        "category": "extra_eu", "vat_rate": "0", "net_cents": italian_net,
        "vat_cents": 0, "gross_cents": italian_net, "vat_code": code, "exemption_note": code["note"],
    }
