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
    return psycopg.connect(database_url, row_factory=dict_row)
