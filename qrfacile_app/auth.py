# /opt/qrfacile/qrfacile_app/auth.py
"""
Compatibility wrapper.

Modulo legacy mantenuto per compatibilità.
La logica reale è centralizzata in auth_core.py
"""

from qrfacile_app.auth_core import (
    COOKIE,
    require_any_role,
)

SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 14  # compat legacy


def require_role(request, role: str):
    return require_any_role(request, (role,))
