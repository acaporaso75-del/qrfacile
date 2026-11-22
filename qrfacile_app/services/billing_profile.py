"""Billing profile of a user: who receives the invoice for module purchases."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Mapping

from fastapi import HTTPException

from qrfacile_app.annual_packages import italian_vat_is_well_formed
from qrfacile_app.pricing_config import EU_VAT_RATES

CUSTOMER_TYPES = ("company", "private", "association")
FIELDS = (
    "customer_type", "country", "name", "vat_number", "fiscal_code", "address", "postcode",
    "city", "province", "sdi", "pec", "invoice_email",
)
VIES_URL = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"
_FISCAL_CODE = re.compile(r"^[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean(value: object, limit: int = 200) -> str:
    return " ".join(str(value or "").split())[:limit]


def _fail(message: str) -> None:
    raise HTTPException(422, message)


def normalize_billing_profile(data: Mapping[str, str]) -> dict:
    profile = {key: _clean(data.get(key)) for key in FIELDS}
    profile["customer_type"] = profile["customer_type"].lower()
    profile["country"] = profile["country"].upper()
    if profile["customer_type"] not in CUSTOMER_TYPES:
        _fail("Indica se sei un'azienda, un privato o un'associazione.")
    if not re.fullmatch(r"[A-Z]{2}", profile["country"]):
        _fail("Indica il Paese (codice di due lettere, ad esempio IT).")
    if not profile["name"]:
        _fail("Indica il nome o la ragione sociale.")
    if profile["invoice_email"] and not _EMAIL.match(profile["invoice_email"]):
        _fail("Email per la fattura non valida.")
    if profile["pec"] and not _EMAIL.match(profile["pec"]):
        _fail("PEC non valida.")
    profile["fiscal_code"] = profile["fiscal_code"].replace(" ", "").upper()
    profile["sdi"] = profile["sdi"].replace(" ", "").upper()
    raw_vat = profile["vat_number"].replace(" ", "").upper()

    if profile["country"] == "IT":
        kind = profile["customer_type"]
        if kind == "company":
            vat = raw_vat.removeprefix("IT")
            if not italian_vat_is_well_formed(vat):
                _fail("Partita IVA non valida: controlla le 11 cifre.")
            profile["vat_number"] = vat
            if profile["sdi"] and not re.fullmatch(r"[A-Z0-9]{7}", profile["sdi"]):
                _fail("Il codice destinatario (SDI) ha 7 caratteri.")
            if not profile["sdi"] and not profile["pec"]:
                _fail("Indica il codice destinatario (SDI) oppure la PEC.")
        elif kind == "private":
            if not _FISCAL_CODE.match(profile["fiscal_code"]):
                _fail("Codice fiscale non valido: deve avere 16 caratteri.")
            profile["vat_number"] = ""
            profile["sdi"] = "0000000"
        else:
            if not re.fullmatch(r"\d{11}", profile["fiscal_code"]) and not _FISCAL_CODE.match(profile["fiscal_code"]):
                _fail("Codice fiscale dell'associazione non valido (11 cifre o 16 caratteri).")
            profile["vat_number"] = raw_vat.removeprefix("IT")
            if profile["vat_number"] and not italian_vat_is_well_formed(profile["vat_number"]):
                _fail("Partita IVA non valida: controlla le 11 cifre.")
            if not profile["sdi"] and not profile["pec"]:
                profile["sdi"] = "0000000"
    else:
        if raw_vat and not re.fullmatch(r"[A-Z0-9]{4,16}", raw_vat):
            _fail("Partita IVA estera non valida.")
        profile["vat_number"] = raw_vat
        profile["sdi"] = "XXXXXXX"
    return profile


def vies_check(country: str, vat_number: str, *, timeout: float = 8.0) -> bool | None:
    """True/False from the EU VIES service; None when it cannot be reached."""
    country = (country or "").upper()
    if country not in EU_VAT_RATES:
        return False
    vies_country = "EL" if country == "GR" else country
    number = re.sub(r"[^A-Z0-9]", "", (vat_number or "").upper())
    if number.startswith(vies_country):
        number = number[len(vies_country):]
    if not number:
        return False
    body = json.dumps({"countryCode": vies_country, "vatNumber": number}).encode()
    request = urllib.request.Request(VIES_URL, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed EU endpoint
            result = json.loads(response.read(100_000).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    valid = result.get("valid")
    return valid if isinstance(valid, bool) else None


def load_billing_profile(cur, user_id: int) -> dict | None:
    cur.execute("SELECT * FROM billing_profiles WHERE user_id=%s", (int(user_id),))
    row = cur.fetchone()
    return dict(row) if row else None


def save_billing_profile(cur, user_id: int, profile: dict) -> None:
    columns = list(FIELDS) + ["vies_valid"]
    values = [profile.get(key) or None for key in FIELDS] + [profile.get("vies_valid")]
    placeholders = ", ".join(["%s"] * (len(columns) + 1))
    updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in columns)
    cur.execute(
        f"INSERT INTO billing_profiles (user_id, {', '.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT (user_id) DO UPDATE SET {updates}, "
        "vies_checked_at=CASE WHEN EXCLUDED.vies_valid IS NULL THEN billing_profiles.vies_checked_at ELSE now() END, "
        "updated_at=now()",
        (int(user_id), *values),
    )
