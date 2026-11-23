import os

import psycopg
from psycopg.rows import dict_row


def pg():
    """Open a database connection using the current process environment.

    Configuration is deliberately resolved at call time: importing domain and
    validation modules must remain possible for offline tooling and unit tests.
    The application still fails explicitly before attempting any database I/O.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for database operations")
    return psycopg.connect(database_url, row_factory=dict_row, connect_timeout=_connect_timeout())


def _connect_timeout() -> int:
    """Seconds to wait for the database: a DB that does not answer (restart,
    network loss) must make the request fail fast instead of hanging a worker."""
    try:
        value = int(os.getenv("QRFACILE_DB_CONNECT_TIMEOUT", "5"))
    except ValueError:
        return 5
    if value <= 0:
        return 5
    return min(value, 60)
