import json
from psycopg.rows import dict_row
from qrfacile_app.db import pg


def audit_log(user: dict | None, action: str, entity_type: str = "", entity_id: int | None = None,
              ip: str = "", user_agent: str = "", meta: dict | None = None) -> None:
    """
    Audit best-effort: non deve mai bloccare il flusso.
    """
    try:
        uid = int(user["id"]) if user and user.get("id") is not None else None
        role = (user.get("role") or "") if user else ""
        meta = meta or {}

        with pg() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO audit_log(user_id, role, action, entity_type, entity_id, ip, user_agent, meta)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                    """,
                    (
                        uid,
                        role or None,
                        action,
                        entity_type or None,
                        int(entity_id) if entity_id else None,
                        ip or None,
                        user_agent or None,
                        json.dumps(meta),
                    ),
                )
            conn.commit()
    except Exception:
        pass

