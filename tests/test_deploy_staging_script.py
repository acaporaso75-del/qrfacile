"""Static guarantees for scripts/deploy_staging.sh.

The staging checkout belongs to the service user while the script runs as
root. Git rejects such repositories ("dubious ownership"), which stopped the
2026-11-21 redeploy before the swap. Every git call must therefore run as the
repository owner through as_repo_owner.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "deploy_staging.sh"


def _code_lines() -> list[str]:
    lines = []
    for raw in SCRIPT.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def test_every_git_command_runs_as_repository_owner():
    offenders = [
        line
        for line in _code_lines()
        if re.search(r"(^|[\s($])git\s", line)
        and "as_repo_owner git" not in line
        and not line.startswith("command -v git")
    ]
    assert offenders == []


def test_repository_owner_is_resolved_from_the_checkout():
    text = SCRIPT.read_text(encoding="utf-8")
    assert """repo_user="$(stat -c '%U' "$root/.git")\"""" in text
    assert 'runuser -u "$repo_user" -- "$@"' in text
    assert 'install -d -m 0700 -o "$repo_user" -g "$repo_group" "$candidate"' in text
    assert "checkout candidato non corrisponde allo SHA richiesto" in text


def test_script_is_valid_bash():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck non installato")
def test_script_passes_shellcheck():
    subprocess.run(["shellcheck", str(SCRIPT)], check=True)
