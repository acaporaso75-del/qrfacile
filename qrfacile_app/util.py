import secrets
import time
import datetime

def now_epoch() -> int:
    return int(time.time())

def day_utc() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")

def new_slug() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))

