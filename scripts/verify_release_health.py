#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


FULL_GIT_SHA = re.compile(r"[0-9a-f]{40}")


def verify_payload(payload: object, *, expected_environment: str, expected_release: str) -> list[str]:
    if not isinstance(payload, dict):
        return ["la risposta health non è un oggetto JSON"]

    expected = {
        "status": "OK",
        "database": "OK",
        "environment": expected_environment,
        "release": expected_release,
    }
    errors = []
    for key, wanted in expected.items():
        actual = payload.get(key)
        if actual != wanted:
            errors.append(f"{key}: atteso {wanted!r}, ricevuto {actual!r}")
    return errors


def fetch_health(url: str, *, timeout: float) -> object:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verifica ambiente e SHA del runtime QRFacile")
    parser.add_argument("--url", required=True, help="Endpoint /healthz da verificare")
    parser.add_argument("--expected-environment", required=True, choices=("staging", "production"))
    parser.add_argument("--expected-release", required=True, help="SHA Git completo atteso")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    expected_release = args.expected_release.strip().lower()
    if not FULL_GIT_SHA.fullmatch(expected_release):
        parser.error("--expected-release deve essere uno SHA Git completo di 40 caratteri")
    if args.timeout <= 0 or args.timeout > 60:
        parser.error("--timeout deve essere maggiore di 0 e non superiore a 60 secondi")

    try:
        payload = fetch_health(args.url, timeout=args.timeout)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"RELEASE_HEALTH_ERROR endpoint non verificabile: {type(exc).__name__}", file=sys.stderr)
        return 2

    errors = verify_payload(
        payload,
        expected_environment=args.expected_environment,
        expected_release=expected_release,
    )
    if errors:
        for error in errors:
            print(f"RELEASE_HEALTH_MISMATCH {error}", file=sys.stderr)
        return 1

    print(
        "RELEASE_HEALTH_OK "
        f"environment={args.expected_environment} release={expected_release}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
