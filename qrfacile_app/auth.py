# /opt/qrfacile/qrfacile_app/auth.py
"""
Compatibility wrapper.

Modulo legacy mantenuto per compatibilità.
La logica reale è centralizzata in auth_core.py
"""

from qrfacile_app.auth_core import (
    COOKIE,
    SESSION_MAX_AGE_SECONDS,
    require_any_role,
)


def require_role(request, role: str):
    return require_any_role(request, (role,))
