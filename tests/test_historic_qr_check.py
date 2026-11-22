"""Printed QR codes must keep working across releases."""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import pytest

from qrfacile_app import main
from scripts import check_historic_qr as chk

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_router_for_old_printed_qr_is_mandatory():
    assert "qrfacile_app.legacy_routes" in main.MANDATORY_ROUTERS


def test_wine_page_shown_as_not_published_counts_as_broken():
    assert chk.classify_wine_page(200, "<h1>Aglianico</h1>") == "ok"
    assert chk.classify_wine_page(200, "<div class='h1'>Etichetta non ancora pubblicata</div>") == "shown_as_not_published"
    assert chk.classify_wine_page(404, "") == "http_404"
    assert chk.classify_legacy_page(200, "<p>Vino</p>") == "ok"
    assert chk.classify_legacy_page(200, "Contenuto legacy importato non disponibile") == "empty_content"


def test_application_route_segments_include_new_pages():
    segments = chk.application_first_segments()
    for name in ("app", "e", "wine", "pricing", "login"):
        assert name in segments
    assert "{legacy_slug}" not in segments


def test_run_reports_collisions_nested_paths_and_broken_pages(monkeypatch):
    pages = {
        "http://x/vecchio-vino": (200, "<p>ok</p>"),
        "http://x/e/AAA?lang=it": (200, "<h1>Vino</h1>"),
        "http://x/e/AAA?lang=en": (200, "<h1>Wine</h1>"),
        "http://x/e/BBB?lang=it": (200, "Etichetta non ancora pubblicata"),
        "http://x/e/BBB?lang=en": (200, "Etichetta non ancora pubblicata"),
    }
    monkeypatch.setattr(chk, "_fetch", lambda url, timeout: pages.get(url, (404, "")))
    report = chk.run(
        "http://x/",
        5,
        legacy=[{"slug": "vecchio-vino"}, {"slug": "wine"}, {"slug": "cantina/rosso"}],
        wines=[{"slug": "AAA", "wine_id": 1}, {"slug": "BBB", "wine_id": 2}],
        app_segments={"wine", "app"},
    )
    outcomes = {row["slug"]: row["outcome"] for row in report["legacy"]}
    assert outcomes == {
        "vecchio-vino": "ok",
        "wine": "collides_with_app_route",
        "cantina/rosso": "nested_path_not_served",
    }
    assert [row["it"] for row in report["wine"]] == ["ok", "shown_as_not_published"]
    assert report["summary"] == {
        "legacy_total": 3, "legacy_broken": 2, "wine_total": 2, "wine_broken": 1, "ok": False,
    }


def _database_url() -> str:
    url = os.getenv("QRFACILE_TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip("QRFACILE_TEST_DATABASE_URL non configurata")
    parsed = urlsplit(url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or not parsed.path.lstrip("/").startswith("qrfacile_test_"):
        pytest.fail("Solo database di test locali")
    return url


@pytest.mark.integration
def test_load_slugs_reads_only_active_pages_and_published_wines():
    url = _database_url()
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")
        conn.execute(
            """
            CREATE TABLE legacy_pages (id serial PRIMARY KEY, slug text, title text, active boolean);
            CREATE TABLE qr_items (id serial PRIMARY KEY, slug text, status text);
            CREATE TABLE qr_wines (id serial PRIMARY KEY, qr_item_id int);
            INSERT INTO legacy_pages (slug, title, active) VALUES ('vecchio', 'Vecchio', TRUE), ('spento', 'Spento', FALSE);
            INSERT INTO qr_items (slug, status) VALUES ('AAA', 'attiva'), ('BBB', 'bozza');
            INSERT INTO qr_wines (qr_item_id) VALUES (1), (2);
            """
        )
    legacy, wines = chk.load_slugs(url)
    assert [row["slug"] for row in legacy] == ["vecchio"]
    assert [row["slug"] for row in wines] == ["AAA"]
