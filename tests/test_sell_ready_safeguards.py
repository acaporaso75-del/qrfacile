from __future__ import annotations

from pathlib import Path
import hashlib

import pytest
from starlette.requests import Request

from qrfacile_app import seo_ui
from qrfacile_app.admin_home_ui import _load_revenue_kpi
from qrfacile_app.legal_core import REQUIRED_LEGAL_DOCUMENTS, record_registration_acceptances
from qrfacile_app.legal_pages import privacy, terms
from qrfacile_app.ui_shell import page_public


ROOT = Path(__file__).resolve().parents[1]


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/register-winery",
            "headers": [(b"user-agent", b"pytest")],
            "query_string": b"",
            "server": ("testserver", 443),
            "client": ("127.0.0.1", 4321),
            "scheme": "https",
        }
    )


class _LegalCursor:
    def __init__(self, *, documents_present: bool = True):
        self.documents_present = documents_present
        self.queries: list[tuple[str, tuple]] = []
        self._last_query = ""

    def execute(self, sql: str, params: tuple):
        self._last_query = sql
        self.queries.append((sql, params))

    def fetchone(self):
        if "FROM legal_documents" in self._last_query:
            return {"title": "Documento test"} if self.documents_present else None
        return None


def test_public_elabel_source_has_no_scan_tracking_or_fingerprinting():
    source = (ROOT / "qrfacile_app" / "public.py").read_text(encoding="utf-8")
    assert "fp_hash" not in source
    assert "qr_scan_dedup" not in source
    assert "track_scan" not in source
    assert '<meta name="robots" content="noindex,nofollow,noarchive">' in source


def test_search_discovery_files_allow_public_content_and_block_private_routes():
    robots = seo_ui.robots_txt().body.decode()
    assert "User-agent: OAI-SearchBot" in robots
    assert "User-agent: GPTBot" in robots
    assert "Disallow: /e/" in robots
    assert "Disallow: /app/" in robots
    assert "Sitemap: https://www.qrfacile.it/sitemap.xml" in robots

    sitemap = seo_ui.sitemap_xml().body.decode()
    assert "https://www.qrfacile.it/wine" in sitemap
    assert "https://www.qrfacile.it/pricing" in sitemap
    assert "https://www.qrfacile.it/e/" not in sitemap

    llms = seo_ui.llms_txt().body.decode()
    assert "do not track visitors" in llms


def test_public_shell_emits_canonical_social_and_structured_metadata():
    html = page_public(
        title="Test",
        subtitle="Test",
        body_html="<p>Test</p>",
        description="Descrizione test",
        canonical_path="/wine",
        structured_data={"@context": "https://schema.org", "@type": "SoftwareApplication"},
    )
    assert '<meta name="description" content="Descrizione test">' in html
    assert '<link rel="canonical" href="https://www.qrfacile.it/wine">' in html
    assert '<meta property="og:url" content="https://www.qrfacile.it/wine">' in html
    assert '<script type="application/ld+json">' in html
    assert 'href="#main-content"' in html
    assert 'id="main-content"' in html


def test_registration_acceptance_records_every_required_version():
    cursor = _LegalCursor()
    record_registration_acceptances(cursor, user_id=42, request=_request())

    inserts = [item for item in cursor.queries if "INSERT INTO legal_acceptances" in item[0]]
    assert len(inserts) == len(REQUIRED_LEGAL_DOCUMENTS)
    assert {params[1:3] for _, params in inserts} == set(REQUIRED_LEGAL_DOCUMENTS.items())


def test_seeded_legal_hashes_match_the_published_html_snapshots():
    migration = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "sql").glob("*.sql")
        if "legal" in path.name or "terms" in path.name
    )
    request = _request()
    for route in (terms, privacy):
        digest = hashlib.sha256(route(request).body).hexdigest()
        assert digest in migration


def test_qr_reference_terms_are_additive_and_preserve_acceptances():
    migration = (ROOT / "sql" / "2026_terms_single_reference_qr.sql").read_text(encoding="utf-8")
    normalized = migration.upper()

    assert migration.startswith("BEGIN;") and migration.rstrip().endswith("COMMIT;")
    assert "'terms',\n    '2026-10-29'" in migration
    assert "ON CONFLICT (document_key, version) DO UPDATE" in migration
    assert "UPDATE legal_documents" in migration
    assert "version <> '2026-10-29'" in migration
    assert "retired_at = TIMESTAMPTZ '2026-10-29 00:00:00+01'" in migration
    assert "DELETE FROM LEGAL_ACCEPTANCES" not in normalized
    assert "UPDATE LEGAL_ACCEPTANCES" not in normalized


def test_registration_fails_closed_when_legal_catalogue_is_missing():
    cursor = _LegalCursor(documents_present=False)
    with pytest.raises(RuntimeError, match="Documento legale obbligatorio non attivo"):
        record_registration_acceptances(cursor, user_id=42, request=_request())


def test_registration_forms_require_terms_and_privacy_acknowledgement():
    for filename in ("winery_register_routes.py", "studio_register_routes.py"):
        source = (ROOT / "qrfacile_app" / filename).read_text(encoding="utf-8")
        assert 'name="terms_accepted"' in source
        assert 'name="privacy_acknowledged"' in source
        assert source.count('value="yes" required') >= 2
        assert "record_registration_acceptances" in source
        assert 'aria-label="{esc(labels.get(name' in source
        assert 'autocomplete="{esc(autocomplete)}"' in source


def test_paid_revenue_is_partitioned_by_payment_environment():
    migration = (ROOT / "sql" / "2026_orders_payment_environment.sql").read_text(encoding="utf-8")
    admin = (ROOT / "qrfacile_app" / "admin_home_ui.py").read_text(encoding="utf-8")
    paypal = (ROOT / "qrfacile_app" / "paypal_ui.py").read_text(encoding="utf-8")

    assert "payment_environment IN ('live', 'sandbox', 'manual', 'unknown')" in migration
    assert "payment_environment='live'" in admin
    assert "payment_environment='sandbox'" in admin
    assert "payment_environment='manual'" in admin
    assert "PAYPAL_MODE" in paypal
    assert "Incassi Live verificati" in admin
    assert "migrazione ambiente pagamenti non applicata" in admin
    assert 'out["revenue_live_eur"] = 0.0' not in admin


class _RevenueCursor:
    def __init__(self, columns, totals=None, legacy_cents=0):
        self.columns = columns
        self.totals = totals or {}
        self.legacy_cents = legacy_cents
        self.last_sql = ""
        self.last_params = ()
        self.queries = []

    def execute(self, sql, params=()):
        self.last_sql = " ".join(sql.split())
        self.last_params = params
        self.queries.append((self.last_sql, params))

    def fetchall(self):
        table = self.last_params[0]
        return [{"column_name": value} for value in self.columns.get(table, set())]

    def fetchone(self):
        if "FROM orders" in self.last_sql:
            return self.totals
        if "FROM credit_orders" in self.last_sql:
            return {"s": self.legacy_cents}
        return {}


def test_admin_revenue_kpi_separates_payment_environments_and_legacy():
    cursor = _RevenueCursor(
        {
            "orders": {"amount_cents", "status", "payment_environment"},
            "credit_orders": {"amount_cents", "status"},
        },
        {
            "live_cents": 12078, "sandbox_cents": 21838,
            "manual_cents": 36478, "unknown_cents": 2900,
        },
        legacy_cents=7900,
    )
    result = {}
    _load_revenue_kpi(cursor, result)
    assert result == {
        "orders_revenue_available": True,
        "revenue_live_eur": 120.78,
        "revenue_sandbox_eur": 218.38,
        "revenue_manual_eur": 364.78,
        "revenue_unknown_eur": 29.0,
        "legacy_revenue_available": True,
        "revenue_legacy_eur": 79.0,
    }


def test_admin_revenue_kpi_reports_missing_migration_instead_of_false_zero():
    cursor = _RevenueCursor({
        "orders": {"amount_cents", "status"},
        "credit_orders": set(),
    })
    result = {}
    _load_revenue_kpi(cursor, result)
    assert result == {
        "orders_revenue_available": False,
        "legacy_revenue_available": False,
    }
    assert not any("FROM orders" in sql for sql, _ in cursor.queries)
