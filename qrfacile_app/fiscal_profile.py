"""Validation for the Italian B2B billing profile used by annual checkout."""
from __future__ import annotations

import re

from fastapi import HTTPException

from qrfacile_app.annual_packages import italian_vat_is_well_formed


def normalized_italian_fiscal_profile(profile: dict) -> dict:
    country = (profile.get("billing_country") or "").strip().upper()
    vat = "".join((profile.get("vat") or "").strip().upper().removeprefix("IT").split())
    province = (profile.get("province") or "").strip().upper()
    cap = "".join((profile.get("billing_cap") or "").split())
    sdi = (profile.get("sdi") or "").strip().upper()
    pec = (profile.get("pec") or "").strip().lower()

    required = {
        "ragione sociale": (profile.get("name") or "").strip(),
        "indirizzo di fatturazione": (profile.get("billing_address") or "").strip(),
        "citta": (profile.get("city") or "").strip(),
    }
    missing = [label for label, value in required.items() if not value]
    if missing:
        raise HTTPException(422, "Completa il profilo fiscale prima dell'acquisto: " + ", ".join(missing) + ".")
    if country != "IT":
        raise HTTPException(422, "Acquisto online disponibile solo per sede fiscale italiana ordinaria; richiedi un preventivo.")
    if not italian_vat_is_well_formed(vat):
        raise HTTPException(422, "Partita IVA italiana non valida nel profilo fiscale.")
    if not re.fullmatch(r"\d{5}", cap):
        raise HTTPException(422, "CAP di fatturazione non valido nel profilo fiscale.")
    if not re.fullmatch(r"[A-Z]{2}", province):
        raise HTTPException(422, "Provincia di fatturazione non valida nel profilo fiscale.")
    if not re.fullmatch(r"[A-Z0-9]{7}", sdi) and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", pec):
        raise HTTPException(422, "Indica un codice SDI di 7 caratteri oppure una PEC valida nel profilo fiscale.")

    return {
        "name": required["ragione sociale"],
        "vat": vat,
        "sdi": sdi,
        "pec": pec,
        "billing_address": required["indirizzo di fatturazione"],
        "city": required["citta"],
        "billing_cap": cap,
        "province": province,
        "billing_country": country,
    }
