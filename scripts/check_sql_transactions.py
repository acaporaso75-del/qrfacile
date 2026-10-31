from __future__ import annotations

from pathlib import Path


def expected_boundaries(path: Path) -> tuple[str, str]:
    if path.name.endswith(("_precheck.sql", "_postcheck.sql")):
        return "BEGIN READ ONLY;", "ROLLBACK;"
    return "BEGIN;", "COMMIT;"


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    for path in sorted((repository / "sql").glob("*.sql")):
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        expected_first, expected_last = expected_boundaries(path)
        if not lines or lines[0] != expected_first or lines[-1] != expected_last:
            failures.append(
                f"{path.name}: atteso {expected_first!r} ... {expected_last!r}"
            )
    if failures:
        raise SystemExit("\n".join(failures))
    print("SQL transaction boundaries: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
