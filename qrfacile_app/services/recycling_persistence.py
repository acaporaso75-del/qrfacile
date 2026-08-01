from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from qrfacile_app.services.recycling_catalog import is_recycling_item_filled


@dataclass(frozen=True)
class RecyclingValue:
    product: str | None
    code: str | None
    extra_code: str | None
    note: str | None


class RecyclingPersistenceError(RuntimeError):
    def __init__(self, component: str):
        self.component = component
        super().__init__(f"Impossibile salvare il componente {component}")


def _optional(value: Any) -> str | None:
    cleaned = " ".join(str(value or "").strip().split())
    return cleaned or None


def normalize_recycling_value(raw: Mapping[str, Any] | None) -> RecyclingValue:
    row = raw or {}
    code = _optional(row.get("code"))
    if code == "-":
        code = None
    return RecyclingValue(
        product=_optional(row.get("product")),
        code=code,
        extra_code=_optional(row.get("extra_code")),
        note=_optional(row.get("note")),
    )


def persist_recycling_component(cur, wine_id: int, component: str, raw: Mapping[str, Any]) -> RecyclingValue:
    """Persist one row and prove that the database contains the expected value.

    Empty UI rows remove old data, including the historic ``code='-'`` placeholder.
    The caller owns the transaction so any raised error rolls back the whole section.
    """
    expected = normalize_recycling_value(raw)
    filled = is_recycling_item_filled(expected.__dict__)

    if not filled:
        cur.execute(
            "DELETE FROM wine_recycle_items WHERE wine_id=%s AND component=%s",
            (int(wine_id), component),
        )
    else:
        cur.execute(
            """
            INSERT INTO wine_recycle_items
              (wine_id, component, code, note, updated_at, product, extra_code)
            VALUES (%s,%s,%s,%s,EXTRACT(EPOCH FROM now())::bigint,%s,%s)
            ON CONFLICT (wine_id, component) DO UPDATE SET
              code=EXCLUDED.code,
              note=EXCLUDED.note,
              updated_at=EXCLUDED.updated_at,
              product=EXCLUDED.product,
              extra_code=EXCLUDED.extra_code
            """,
            (int(wine_id), component, expected.code, expected.note, expected.product, expected.extra_code),
        )
        if cur.rowcount != 1:
            raise RecyclingPersistenceError(component)

    cur.execute(
        """
        SELECT product, code, extra_code, note
        FROM wine_recycle_items
        WHERE wine_id=%s AND component=%s
        LIMIT 1
        """,
        (int(wine_id), component),
    )
    stored_row = cur.fetchone()
    if not filled:
        if stored_row is not None:
            raise RecyclingPersistenceError(component)
        return expected

    stored = normalize_recycling_value(stored_row)
    if stored != expected:
        raise RecyclingPersistenceError(component)
    return stored
