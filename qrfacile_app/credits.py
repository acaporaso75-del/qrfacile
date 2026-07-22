import time
from typing import Dict, Optional

CREDIT_WINE = "wine"
CREDIT_EVENT = "event"
CREDIT_GENERIC = "generic"

def now_epoch() -> int:
    return int(time.time())

def get_balances(cur, user_id: int) -> Dict[str, int]:
    cur.execute("""
      SELECT credit_type, balance
      FROM credit_balance
      WHERE user_id=%s
    """, (int(user_id),))
    out = {r["credit_type"]: int(r["balance"]) for r in cur.fetchall()}
    out.setdefault(CREDIT_WINE, 0)
    out.setdefault(CREDIT_EVENT, 0)
    out.setdefault(CREDIT_GENERIC, 0)
    return out

def add_credit(cur, user_id: int, credit_type: str, delta: int, reason: str = "", ref_table: str = "", ref_id: Optional[int] = None):
    cur.execute("""
      INSERT INTO credit_ledger(user_id, credit_type, delta, reason, ref_table, ref_id, created_at)
      VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (int(user_id), credit_type, int(delta), reason or None, ref_table or None, ref_id, now_epoch()))

def seed_free_labels_if_needed(cur, user_id: int, wine_credits: int = 5, generic_credits: int = 1, event_credits: int = 0):
    cur.execute("SELECT 1 FROM credit_ledger WHERE user_id=%s AND reason='seed' LIMIT 1", (int(user_id),))
    if cur.fetchone():
        return
    if wine_credits:
        add_credit(cur, user_id, CREDIT_WINE, int(wine_credits), reason="seed")
    if generic_credits:
        add_credit(cur, user_id, CREDIT_GENERIC, int(generic_credits), reason="seed")
    if event_credits:
        add_credit(cur, user_id, CREDIT_EVENT, int(event_credits), reason="seed")

def auto_unfreeze_events(cur):
    return

def add_user_credits(cur, user_id: int, delta_free: int = 0, delta_paid: int = 0, reason: str = "", ref: str = ""):
    delta = int(delta_free) + int(delta_paid)
    if delta:
        add_credit(cur, user_id, CREDIT_WINE, delta, reason=reason or ref or "admin_adjust")
