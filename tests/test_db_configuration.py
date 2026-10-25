import importlib

import pytest


def test_database_module_can_be_imported_without_runtime_configuration(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    database = importlib.import_module("qrfacile_app.db")

    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        database.pg()
