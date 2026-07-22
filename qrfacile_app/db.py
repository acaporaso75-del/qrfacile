import os
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL missing in /opt/qrfacile-staging/.env")

def pg():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)
