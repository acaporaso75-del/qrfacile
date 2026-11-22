"""Declared vertical modules and the URL prefixes they own."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Module:
    key: str
    label: str
    prefix: str
    content_types: tuple[str, ...]
    credit_type: str


MODULES: dict[str, Module] = {
    "link": Module("link", "QRFacile Link", "d", ("link", "pdf", "minipage"), "generic"),
}

# One-letter public prefixes: e = Wine, d = Link, r = Menu Ristorante (reserved).
RESERVED_PREFIXES = frozenset({"e", "d", "r"})
