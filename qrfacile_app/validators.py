from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, Dict
import math
import re

DEC_RE = re.compile(r"^\s*-?\d+([.,]\d+)?\s*$")

@dataclass
class FieldError:
    field: str
    msg: str

def _norm_num(s: str) -> str:
    return s.strip().replace(",", ".")

def parse_int(field: str, s: str, min_v: int = 0, max_v: int = 100000) -> Tuple[Optional[int], Optional[FieldError]]:
    s = (s or "").strip()
    if s == "":
        return None, FieldError(field, "Obbligatorio")
    if not re.match(r"^\d+$", s):
        return None, FieldError(field, "Inserisci un numero intero")
    v = int(s)
    if v < min_v:
        return None, FieldError(field, f"Min {min_v}")
    if v > max_v:
        return None, FieldError(field, f"Max {max_v}")
    return v, None

def parse_decimal(field: str, s: str, decimals: int = 2, min_v: float = 0.0, max_v: float = 9999.0, required: bool = True) -> Tuple[Optional[float], Optional[FieldError]]:
    s = (s or "").strip()
    if s == "":
        if required:
            return None, FieldError(field, "Obbligatorio")
        return None, None
    if not DEC_RE.match(s):
        return None, FieldError(field, "Numero non valido")
    v = float(_norm_num(s))
    if v < min_v:
        return None, FieldError(field, f"Min {min_v}")
    if v > max_v:
        return None, FieldError(field, f"Max {max_v}")
    v = round(v, decimals)
    return v, None

def validate_nutrition(payload: Dict[str, str]) -> Tuple[Dict[str, Optional[float]], list[FieldError]]:
    """
    Expected keys:
      energy_kj, energy_kcal, fat, saturates, carbs, sugars, protein, salt
    """
    errs: list[FieldError] = []
    out: Dict[str, Optional[float]] = {}

    ekj, e = parse_int("energy_kj", payload.get("energy_kj",""), min_v=0, max_v=5000)
    if e: errs.append(e)
    out["energy_kj"] = ekj

    ekcal, e = parse_int("energy_kcal", payload.get("energy_kcal",""), min_v=0, max_v=2000)
    if e: errs.append(e)
    out["energy_kcal"] = ekcal

    fat, e = parse_decimal("fat", payload.get("fat",""), decimals=2, min_v=0, max_v=50)
    if e: errs.append(e)
    out["fat"] = fat

    sat, e = parse_decimal("saturates", payload.get("saturates",""), decimals=2, min_v=0, max_v=50)
    if e: errs.append(e)
    out["saturates"] = sat

    carbs, e = parse_decimal("carbs", payload.get("carbs",""), decimals=2, min_v=0, max_v=50)
    if e: errs.append(e)
    out["carbs"] = carbs

    sug, e = parse_decimal("sugars", payload.get("sugars",""), decimals=2, min_v=0, max_v=50)
    if e: errs.append(e)
    out["sugars"] = sug

    prot, e = parse_decimal("protein", payload.get("protein",""), decimals=2, min_v=0, max_v=50)
    if e: errs.append(e)
    out["protein"] = prot

    salt, e = parse_decimal("salt", payload.get("salt",""), decimals=3, min_v=0, max_v=10)
    if e: errs.append(e)
    out["salt"] = salt

    # Coerenze (solo se i valori ci sono)
    if fat is not None and sat is not None and sat > fat:
        errs.append(FieldError("saturates", "Non può superare i grassi"))
    if carbs is not None and sug is not None and sug > carbs:
        errs.append(FieldError("sugars", "Non può superare i carboidrati"))

    # kcal ~ kJ/4.184 (soft check)
    if ekj is not None and ekcal is not None and ekj > 0:
        expected = ekj / 4.184
        if expected > 0:
            diff = abs(ekcal - expected) / expected
            if diff > 0.25:  # 25% tolleranza
                errs.append(FieldError("energy_kcal", "Valore insolito rispetto ai kJ (controlla)"))

    return out, errs

def validate_recycle_code(code: str) -> Tuple[Optional[str], Optional[FieldError]]:
    code = (code or "").strip()
    if not code:
        return None, FieldError("code", "Codice obbligatorio")
    # soft: allow many formats, just cap length and reject weird chars
    if len(code) > 40:
        return None, FieldError("code", "Troppo lungo")
    if not re.match(r"^[A-Za-z0-9/,\-\s]+$", code):
        return None, FieldError("code", "Caratteri non validi")
    return code, None

