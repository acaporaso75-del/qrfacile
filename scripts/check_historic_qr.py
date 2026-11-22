"""Check that every QR already printed on bottles still opens its page.

Read-only. Two families of printed QR codes are checked:

- legacy WordPress pages imported in ``legacy_pages`` (``/<slug>``), served
  by the catch-all router in ``legacy_routes``;
- QRFacile wine pages (``/e/<slug>``) whose ``qr_items.status`` is ``attiva``;
- QRFacile Link codes (``/d/<slug>``, beta ``qr_type='external'`` rows and
  ``module='link'`` rows) that are ``attiva``: a redirect (3xx) counts as
  working, the destination site itself is not fetched.

A page counts as working only if it answers 200 **and** shows its content:
a wine page that renders "Etichetta non ancora pubblicata" (also HTTP 200)
is reported as broken, because the bottle QR no longer shows the label.
Legacy slugs that collide with an application route are reported too: the
application route wins and the printed QR would open the wrong page.

DATABASE_URL is read from the environment and never printed. The output
contains slugs and HTTP outcomes only, no personal data.

Usage:
    python scripts/check_historic_qr.py --base-url http://127.0.0.1:8000 [--json report.json]
Exit code 0 = all working, 1 = at least one broken or colliding QR.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NOT_PUBLISHED_MARKERS = ("Etichetta non ancora pubblicata", "Label not yet published")
# Continuity notice: the page works for consumers but data is missing and the
# winery should complete it. Reported, not counted as broken.
BEING_UPDATED_MARKERS = ("in aggiornamento da parte del produttore", "being updated by the producer")
LEGACY_NOT_FOUND_MARKERS = ("Legacy page not found", "Contenuto legacy importato non disponibile")


def _fetch(url: str, timeout: float) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "qrfacile-historic-qr-check"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-given base URL
            return response.status, response.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, f"network error: {type(exc).__name__}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - keep the 3xx as the answer
        return None


def _fetch_status(url: str, timeout: float) -> int:
    """HTTP status without following redirects (Link codes point off-site)."""
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": "qrfacile-historic-qr-check"})
    try:
        with opener.open(request, timeout=timeout) as response:  # noqa: S310 - operator-given base URL
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0


def classify_link_code(status: int) -> str:
    return "ok" if 200 <= status < 400 else f"http_{status}"


def classify_wine_page(status: int, body: str) -> str:
    if status != 200:
        return f"http_{status}"
    if any(marker in body for marker in NOT_PUBLISHED_MARKERS):
        return "shown_as_not_published"
    if any(marker in body for marker in BEING_UPDATED_MARKERS):
        return "ok_data_being_updated"
    return "ok"


def classify_legacy_page(status: int, body: str) -> str:
    if status != 200:
        return f"http_{status}"
    if any(marker in body for marker in LEGACY_NOT_FOUND_MARKERS):
        return "empty_content"
    return "ok"


def application_first_segments() -> set[str]:
    """First path segment of every concrete application route."""
    os.environ.setdefault("APP_ENV", "test")
    from qrfacile_app.main import app  # imported lazily: needs the runtime env

    def walk(routes):
        for route in routes:
            # FastAPI >= 0.16x keeps included routers as wrappers that expose
            # the original router instead of flattening their routes.
            nested = getattr(route, "original_router", None)
            if nested is not None:
                yield from walk(getattr(nested, "routes", []))
            else:
                yield route

    # Static mounts may be absent where the directory is missing; the legacy
    # router refuses these names anyway.
    segments: set[str] = {"static", "uploads", "favicon.ico"}
    for route in walk(app.routes):
        path = getattr(route, "path", "") or ""
        first = path.strip("/").split("/", 1)[0]
        if first and "{" not in first:
            segments.add(first)
    return segments


def load_slugs(database_url: str) -> tuple[list[dict], list[dict]]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT slug, title FROM legacy_pages WHERE active=TRUE ORDER BY slug"
            )
            legacy = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT qi.slug, qw.id AS wine_id
                FROM qr_items qi
                JOIN qr_wines qw ON qw.qr_item_id = qi.id
                WHERE lower(qi.status) = 'attiva'
                ORDER BY qw.id
                """
            )
            wines = [dict(row) for row in cur.fetchall()]
    return legacy, wines


def load_link_slugs(database_url: str) -> list[dict]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT q.slug FROM qr_items q
                WHERE lower(q.status) = 'attiva'
                  AND (q.qr_type = 'external' OR to_jsonb(q)->>'module' = 'link')
                ORDER BY q.id
                """
            )
            return [dict(row) for row in cur.fetchall()]


def run(
    base_url: str,
    timeout: float,
    legacy: list[dict],
    wines: list[dict],
    app_segments: set[str],
    links: list[dict] | None = None,
) -> dict:
    base = base_url.rstrip("/")
    results = {"legacy": [], "wine": [], "link": []}
    for row in legacy:
        slug = str(row.get("slug") or "").strip().strip("/")
        if "/" in slug:
            outcome = "nested_path_not_served"
        elif slug in app_segments:
            outcome = "collides_with_app_route"
        else:
            outcome = classify_legacy_page(*_fetch(f"{base}/{slug}", timeout))
        results["legacy"].append({"slug": slug, "outcome": outcome})
    for row in wines:
        slug = str(row.get("slug") or "").strip()
        outcomes = {}
        for lang in ("it", "en"):
            outcomes[lang] = classify_wine_page(*_fetch(f"{base}/e/{slug}?lang={lang}", timeout))
        results["wine"].append({"slug": slug, "wine_id": row.get("wine_id"), **outcomes})
    for row in links or []:
        slug = str(row.get("slug") or "").strip()
        results["link"].append({"slug": slug, "outcome": classify_link_code(_fetch_status(f"{base}/d/{slug}", timeout))})
    broken_legacy = [r for r in results["legacy"] if r["outcome"] != "ok"]
    broken_link = [r for r in results["link"] if r["outcome"] != "ok"]
    working = {"ok", "ok_data_being_updated"}
    broken_wine = [r for r in results["wine"] if r["it"] not in working or r["en"] not in working]
    to_complete = [r for r in results["wine"] if "ok_data_being_updated" in (r["it"], r["en"])]
    results["summary"] = {
        "legacy_total": len(results["legacy"]),
        "legacy_broken": len(broken_legacy),
        "wine_total": len(results["wine"]),
        "wine_broken": len(broken_wine),
        "wine_data_to_complete": len(to_complete),
        "ok": not broken_legacy and not broken_wine and not broken_link,
    }
    if links is not None:
        results["summary"]["link_total"] = len(results["link"])
        results["summary"]["link_broken"] = len(broken_link)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--json", type=Path, help="write the full report here")
    args = parser.parse_args(argv)

    database_url = (os.environ.get("DATABASE_URL") or os.environ.get("QRFACILE_DB_DSN") or "").strip()
    if not database_url:
        print("HISTORIC_QR_ERROR DATABASE_URL non configurata", file=sys.stderr)
        return 2
    legacy, wines = load_slugs(database_url)
    links = load_link_slugs(database_url)
    report = run(args.base_url, args.timeout, legacy, wines, application_first_segments(), links=links)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = report["summary"]
    for family in ("legacy", "wine", "link"):
        for row in report[family]:
            outcomes = {row.get("outcome", "ok"), row.get("it", "ok"), row.get("en", "ok")}
            if outcomes - {"ok", "ok_data_being_updated"}:
                print(f"BROKEN {family} {json.dumps(row, ensure_ascii=False)}")
            elif "ok_data_being_updated" in outcomes:
                print(f"TO_COMPLETE {family} {json.dumps(row, ensure_ascii=False)}")
    print(
        ("HISTORIC_QR_OK" if summary["ok"] else "HISTORIC_QR_BROKEN")
        + f" legacy={summary['legacy_total']}/broken={summary['legacy_broken']}"
        + f" wine={summary['wine_total']}/broken={summary['wine_broken']}"
        + f"/to_complete={summary['wine_data_to_complete']}"
        + f" link={summary.get('link_total', 0)}/broken={summary.get('link_broken', 0)}"
    )
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
