"""One account, several modules: first-access choice, activation, last module used."""
from __future__ import annotations

import asyncio  # noqa: F401
from types import SimpleNamespace

import psycopg
import pytest
from psycopg.rows import dict_row

from qrfacile_app import auth_routes, ui_shell
from qrfacile_app.modules import switches
from tests.test_vertical_modules_migration import MIGRATION, _database_url


def test_landing_follows_last_module_and_role():
    landing = auth_routes.default_landing
    assert landing("business") == "/app/start"            # first access: choose
    assert landing("winery") == "/app/dashboard"           # existing wineries unchanged
    assert landing("studio") == "/app/start"
    assert landing("business", "link") == "/app/link"
    assert landing("winery", "link") == "/app/link"
    assert landing("business", "wine") == "/app/dashboard"
    assert landing("winery", "bogus") == "/app/dashboard"


def test_login_reads_last_module_without_requiring_the_column():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "qrfacile_app" / "auth_routes.py").read_text(encoding="utf-8")
    assert "to_jsonb(users)->>'last_module' AS last_module" in source
    assert 'next_url = default_landing(u.get("role") or "", u.get("last_module"))' in source


def test_business_sidebar_offers_my_modules():
    html = ui_shell._sidebar("business", "b@example.test", {"wine": 0, "generic": 3})
    assert 'href="/app/start"' in html and "I miei moduli" in html
    assert 'href="/app/dashboard"' not in html


@pytest.fixture()
def db(monkeypatch):
    url = _database_url()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(
            """
            CREATE TABLE users (id bigserial PRIMARY KEY, email text, role text NOT NULL);
            INSERT INTO users (email, role) VALUES ('bar@example.test', 'winery');
            CREATE TABLE qr_items (id bigserial PRIMARY KEY, owner_user_id bigint, qr_type text, status text,
                                   slug text UNIQUE, payload jsonb);
            CREATE TABLE wineries (id bigserial PRIMARY KEY, owner_user_id bigint, name text, billing_country text,
                                   created_at bigint);
            CREATE TABLE credit_ledger (id bigserial PRIMARY KEY, user_id bigint, credit_type text, delta int,
                                        reason text, ref_table text, ref_id bigint, created_at bigint);
            CREATE VIEW available_credit_ledger AS SELECT * FROM credit_ledger;
            CREATE TABLE legal_acceptances (id bigserial PRIMARY KEY, user_id bigint, document_key text,
              document_version text, accepted_at timestamptz DEFAULT now(), ip_address inet, user_agent text,
              evidence jsonb DEFAULT '{}'::jsonb, UNIQUE (user_id, document_key, document_version));
            """
        )
        conn.execute(MIGRATION.read_text(encoding="utf-8"))
        conn.execute("UPDATE users SET role='business', display_name='Bar Sport' WHERE id=1")

    from qrfacile_app.modules import account

    user = {"id": 1, "email": "bar@example.test", "role": "business"}
    monkeypatch.setattr(account, "pg", lambda: psycopg.connect(url, row_factory=dict_row))
    monkeypatch.setattr(account, "require_any_role", lambda *a, **k: dict(user))
    monkeypatch.setattr(account, "csrf_input", lambda request: "")
    monkeypatch.setattr(account, "require_csrf_or_same_origin", lambda request: None)
    monkeypatch.setattr(switches, "is_enabled", lambda key: True)

    def sql(query, params=()):
        with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
            cur = conn.execute(query, params)
            return cur.fetchall() if cur.description else None

    return SimpleNamespace(account=account, sql=sql, user=user, url=url)


REQUEST = SimpleNamespace(headers={}, cookies={}, client=None,
                          app=SimpleNamespace(state=SimpleNamespace(app_base_url="https://x")),
                          url=SimpleNamespace(scheme="https"))


@pytest.mark.integration
def test_user_modules_reflect_activation(db):
    with psycopg.connect(db.url, row_factory=dict_row) as conn, conn.cursor() as cur:
        assert db.account.user_modules(cur, db.user) == {"wine": False, "link": False}
    db.sql("INSERT INTO legal_acceptances (user_id, document_key, document_version) VALUES "
           "(1,'terms','2026-12-link'),(1,'privacy','2026-12-link')")
    with psycopg.connect(db.url, row_factory=dict_row) as conn, conn.cursor() as cur:
        assert db.account.user_modules(cur, db.user) == {"wine": False, "link": True}
        assert db.account.user_modules(cur, {"id": 1, "role": "winery"})["wine"] is True


@pytest.mark.integration
def test_business_activates_wine_and_gets_free_wine_credits(db):
    html = db.account.wine_activate_get(REQUEST).body.decode()
    assert 'value="Bar Sport"' in html and 'action="/app/modules/wine/activate"' in html
    response = db.account.wine_activate_post(REQUEST, name="Cantina Bar Sport")
    assert response.status_code == 303 and response.headers["location"] == "/app/dashboard"
    assert db.sql("SELECT role, last_module FROM users WHERE id=1") == [{"role": "winery", "last_module": "wine"}]
    assert db.sql("SELECT name, owner_user_id FROM wineries") == [{"name": "Cantina Bar Sport", "owner_user_id": 1}]
    assert db.sql("SELECT credit_type, delta, reason FROM credit_ledger") == [
        {"credit_type": "wine", "delta": 3, "reason": "seed"}]
    # Twice is harmless: no second winery, no second gift.
    db.user["role"] = "winery"
    again = db.account.wine_activate_post(REQUEST, name="Altro")
    assert again.headers["location"] == "/app/dashboard"
    assert db.sql("SELECT COUNT(*) AS n FROM wineries")[0]["n"] == 1
    assert db.sql("SELECT COUNT(*) AS n FROM credit_ledger")[0]["n"] == 1


@pytest.mark.integration
def test_wine_activation_requires_a_name(db):
    response = db.account.wine_activate_post(REQUEST, name="  ")
    assert "err=" in response.headers["location"]
    assert db.sql("SELECT role FROM users WHERE id=1")[0]["role"] == "business"


def test_choosing_a_module_remembers_it(monkeypatch):
    from qrfacile_app import start_ui

    remembered = []
    monkeypatch.setattr(start_ui, "require_any_role", lambda *a, **k: {"id": 1, "email": "b@x", "role": "business"})
    monkeypatch.setattr(start_ui, "require_csrf_or_same_origin", lambda request: None)
    monkeypatch.setattr(start_ui, "remember_module", lambda user_id, key: remembered.append((user_id, key)))
    assert start_ui.select_mode(REQUEST, mode="link").headers["location"] == "/app/link"
    assert start_ui.select_mode(REQUEST, mode="wine_activate").headers["location"] == "/app/modules/wine/activate"
    assert start_ui.select_mode(REQUEST, mode="dashboard").headers["location"] == "/app/start"  # no winery yet
    monkeypatch.setattr(start_ui, "require_any_role", lambda *a, **k: {"id": 2, "email": "w@x", "role": "winery"})
    assert start_ui.select_mode(REQUEST, mode="dashboard").headers["location"] == "/app/dashboard"
    assert remembered == [(1, "link"), (2, "wine")]


def test_start_page_for_business_shows_activation(monkeypatch):
    from qrfacile_app import start_ui

    monkeypatch.setattr(start_ui, "require_any_role", lambda *a, **k: {"id": 1, "email": "b@x", "role": "business"})
    monkeypatch.setattr(start_ui, "pg", lambda: (_ for _ in ()).throw(RuntimeError("no db")))
    monkeypatch.setattr(start_ui, "modules_for", lambda user: {"wine": False, "link": True})
    monkeypatch.setattr(switches, "is_enabled", lambda key: True)
    html = start_ui.start(REQUEST).body.decode()
    assert 'value="wine_activate"' in html and "Attiva Wine" in html
    assert 'value="link"' in html and "QR vino disponibili" not in html
