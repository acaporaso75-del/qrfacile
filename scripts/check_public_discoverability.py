#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qrfacile_app.seo_ui import PRIVATE_PATHS, PUBLIC_BASE_URL, PUBLIC_PAGES


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.canonical = ""
        self.robots = ""
        self.og_url = ""
        self.description = ""
        self.structured_data = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        values = {str(key).lower(): str(value or "") for key, value in attrs}
        if tag.lower() == "link" and "canonical" in values.get("rel", "").lower().split():
            self.canonical = values.get("href", "")
        if tag.lower() == "meta":
            if values.get("name", "").lower() == "robots":
                self.robots = values.get("content", "")
            if values.get("name", "").lower() == "description":
                self.description = values.get("content", "")
            if values.get("property", "").lower() == "og:url":
                self.og_url = values.get("content", "")
        if tag.lower() == "script" and values.get("type", "").lower() == "application/ld+json":
            self.structured_data += 1


def _read_response(response, *, max_bytes: int = 2_000_000) -> tuple[str, dict[str, str]]:
    body = response.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ValueError("response_too_large")
    charset = response.headers.get_content_charset() or "utf-8"
    return body.decode(charset), {key.lower(): value for key, value in response.headers.items()}


def fetch(base_url: str, path: str, *, timeout: float) -> tuple[str, dict[str, str]]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    request = Request(url, headers={"Accept": "text/html,application/xml,text/plain", "User-Agent": "QRFacile-release-preflight/1"})
    with urlopen(request, timeout=timeout) as response:
        return _read_response(response)


def verify_robots(body: str) -> list[str]:
    errors = []
    for agent in ("*", "OAI-SearchBot", "GPTBot"):
        if f"User-agent: {agent}" not in body:
            errors.append(f"robots_missing_agent:{agent}")
    for path in PRIVATE_PATHS:
        if f"Disallow: {path}" not in body:
            errors.append(f"robots_missing_disallow:{path}")
    if f"Sitemap: {PUBLIC_BASE_URL}/sitemap.xml" not in body:
        errors.append("robots_missing_canonical_sitemap")
    return errors


def verify_sitemap(body: str) -> list[str]:
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        return ["sitemap_invalid_xml"]
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locations = {str(node.text or "").strip() for node in root.findall("sm:url/sm:loc", namespace)}
    expected = {f"{PUBLIC_BASE_URL}{path}" for path, _priority in PUBLIC_PAGES}
    errors = [f"sitemap_missing:{url}" for url in sorted(expected - locations)]
    if any(urlparse(url).path.startswith(PRIVATE_PATHS) for url in locations):
        errors.append("sitemap_contains_private_path")
    return errors


def verify_llms(body: str) -> list[str]:
    errors = []
    for required in ("# QRFACILE", f"{PUBLIC_BASE_URL}/wine", f"{PUBLIC_BASE_URL}/pricing", "human review"):
        if required not in body:
            errors.append(f"llms_missing:{required}")
    return errors


def verify_public_page(path: str, body: str, headers: dict[str, str]) -> list[str]:
    parser = _MetadataParser()
    parser.feed(body)
    expected = f"{PUBLIC_BASE_URL}{path}"
    errors = []
    if parser.canonical != expected:
        errors.append(f"page_canonical_mismatch:{path}")
    if parser.og_url != expected:
        errors.append(f"page_og_url_mismatch:{path}")
    if "noindex" in parser.robots.lower() or "noindex" in headers.get("x-robots-tag", "").lower():
        errors.append(f"page_noindex:{path}")
    if not parser.description.strip():
        errors.append(f"page_missing_description:{path}")
    if parser.structured_data < 1:
        errors.append(f"page_missing_structured_data:{path}")
    return errors


def _validated_base_url(parser: argparse.ArgumentParser, value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        parser.error("--base-url deve essere un'origine HTTPS senza credenziali")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        parser.error("--base-url non deve contenere path, query o fragment")
    return f"https://{parsed.netloc}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica SEO e discoverability pubblica senza modificare il sito")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    base_url = _validated_base_url(parser, args.base_url)
    if args.timeout <= 0 or args.timeout > 60:
        parser.error("--timeout deve essere maggiore di 0 e non superiore a 60")

    checks = {
        "/robots.txt": verify_robots,
        "/sitemap.xml": verify_sitemap,
        "/llms.txt": verify_llms,
    }
    errors: list[str] = []
    for path, verifier in checks.items():
        try:
            body, _headers = fetch(base_url, path, timeout=args.timeout)
            errors.extend(verifier(body))
        except (HTTPError, URLError, TimeoutError, UnicodeError, ValueError) as exc:
            errors.append(f"fetch_failed:{path}:{type(exc).__name__}")
    for path, _priority in PUBLIC_PAGES:
        try:
            body, headers = fetch(base_url, path, timeout=args.timeout)
            errors.extend(verify_public_page(path, body, headers))
        except (HTTPError, URLError, TimeoutError, UnicodeError, ValueError) as exc:
            errors.append(f"fetch_failed:{path}:{type(exc).__name__}")

    if errors:
        for error in errors:
            print(f"PUBLIC_DISCOVERABILITY_MISMATCH {error}", file=sys.stderr)
        return 1
    print(f"PUBLIC_DISCOVERABILITY_OK origin={base_url} pages={len(PUBLIC_PAGES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
