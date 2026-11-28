"""A module must not define the same top-level function twice.

A silent duplicate made external_qr_ui keep an old, unsafe page after a fix
(only the last definition is bound to the name), and studio_settings_ui
carried four dead copies.
"""
from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_module_defines_a_function_twice():
    offenders = {}
    for path in sorted((ROOT / "qrfacile_app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        duplicated = sorted(name for name, count in Counter(names).items() if count > 1)
        if duplicated:
            offenders[str(path.relative_to(ROOT))] = duplicated
    assert offenders == {}
