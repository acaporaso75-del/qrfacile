import json
from psycopg.rows import dict_row
from qrfacile_app.util import now_epoch

def record_label_snapshot(cur, label_id: int, actor_user_id: int | None, action: str) -> None:
    """
    Salva uno snapshot dei campi principali di wine_labels (versioning).
    """
    cur.execute("""
      SELECT id, wine_id, winery_id, qr_item_id,
             label_type, language, lot_override, title_override,
             active, public_enabled, published_at, created_at, updated_at,
             created_by_user_id
      FROM wine_labels
      WHERE id=%s
      LIMIT 1
    """, (int(label_id),))
    row = cur.fetchone()
    if not row:
        return

    snapshot = dict(row)
    cur.execute("""
      INSERT INTO wine_label_history(wine_label_id, actor_user_id, action, snapshot, created_at)
      VALUES (%s,%s,%s,%s::jsonb,%s)
    """, (int(label_id), actor_user_id, action, json.dumps(snapshot, ensure_ascii=False), now_epoch()))

def rollback_label(cur, label_id: int, history_id: int) -> None:
    """
    Ripristina wine_labels dai campi nello snapshot (solo campi sicuri).
    """
    cur.execute("""
      SELECT snapshot
      FROM wine_label_history
      WHERE id=%s AND wine_label_id=%s
      LIMIT 1
    """, (int(history_id), int(label_id)))
    r = cur.fetchone()
    if not r:
        raise ValueError("History not found")

    snap = r["snapshot"] or {}
    # Ripristiniamo SOLO campi controllati
    cur.execute("""
      UPDATE wine_labels
      SET label_type=%s,
          language=%s,
          lot_override=%s,
          title_override=%s,
          active=%s,
          public_enabled=%s,
          published_at=%s,
          updated_at=%s
      WHERE id=%s
    """, (
        snap.get("label_type"),
        snap.get("language"),
        snap.get("lot_override"),
        snap.get("title_override"),
        bool(snap.get("active", True)),
        bool(snap.get("public_enabled", False)),
        snap.get("published_at"),
        now_epoch(),
        int(label_id),
    ))
