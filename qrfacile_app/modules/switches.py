"""On/off switches for modules, stored in module_switches (admin managed)."""
from __future__ import annotations

import time

from fastapi import HTTPException

from qrfacile_app.db import pg

_CACHE_SECONDS = 10.0
_cache: dict[str, tuple[float, bool]] = {}


def clear_cache() -> None:
    _cache.clear()


def is_enabled(key: str) -> bool:
    """True only when the switch exists and is on; False on any error."""
    cached = _cache.get(key)
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]
    try:
        with pg() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT enabled FROM module_switches WHERE key=%s", (key,))
                row = cur.fetchone()
    except Exception:
        # Cache the failure too: before the migration every page would
        # otherwise open a connection and log a failing query.
        _cache[key] = (now, False)
        return False
    if isinstance(row, dict):
        value = bool(row.get("enabled"))
    else:
        value = bool(row[0]) if row else False
    _cache[key] = (now, value)
    return value


def set_enabled(key: str, enabled: bool, *, user_id: int) -> None:
    with pg() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE module_switches SET enabled=%s, updated_by=%s, updated_at=now() WHERE key=%s",
                (bool(enabled), int(user_id), key),
            )
            if cur.rowcount != 1:
                raise KeyError(key)
            cur.execute(
                """
                INSERT INTO audit_log (user_id, role, action, entity_type, entity_id, ip, user_agent, meta, created_at)
                VALUES (%s, 'admin', 'module_switch_changed', 'module_switches', NULL, NULL, 'admin-modules',
                        jsonb_build_object('key', %s::text, 'enabled', %s::boolean), now())
                """,
                (int(user_id), key, bool(enabled)),
            )
        conn.commit()
    clear_cache()


def migration_applied() -> bool:
    """True once sql/2026_vertical_modules_base.sql has created module_switches."""
    cached = _cache.get("__migration__")
    now = time.monotonic()
    if cached and now - cached[0] < _CACHE_SECONDS:
        return cached[1]
    try:
        with pg() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('module_switches') IS NOT NULL")
                row = cur.fetchone()
        value = bool(row[0] if not isinstance(row, dict) else next(iter(row.values())))
    except Exception:
        value = False
    _cache["__migration__"] = (now, value)
    return value


def require_module(key: str, user: dict) -> None:
    """Hide a switched-off module (404) from everyone but admins."""
    if (user.get("role") or "").lower().strip() == "admin":
        return
    if not is_enabled(key):
        raise HTTPException(404, "Not found")
