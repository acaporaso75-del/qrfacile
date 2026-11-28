from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_tracked_shell_scripts_use_lf_only() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", "*.sh"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = [ROOT / item for item in result.stdout.splitlines() if item]
    assert paths, "nessuno script shell trovato"

    offenders = [str(path.relative_to(ROOT)) for path in paths if b"\r" in path.read_bytes()]
    assert offenders == [], f"script shell con CR/CRLF: {offenders}"
