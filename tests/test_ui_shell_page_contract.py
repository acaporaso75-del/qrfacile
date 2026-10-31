import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_KEYWORDS = {"title", "subtitle", "body_html"}
ALLOWED_KEYWORDS = REQUIRED_KEYWORDS | {
    "actions_html", "msg", "err", "user_email", "role", "credits"
}


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _page_contract_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    direct_names: set[str] = set()
    module_names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (
            node.module == "qrfacile_app.ui_shell"
            or (node.level == 1 and node.module == "ui_shell")
        ):
            direct_names.update(
                item.asname or item.name for item in node.names if item.name == "page"
            )
        elif isinstance(node, ast.Import):
            module_names.update(
                item.asname or item.name
                for item in node.names
                if item.name == "qrfacile_app.ui_shell"
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module == "qrfacile_app"
        ):
            module_names.update(
                item.asname or item.name for item in node.names if item.name == "ui_shell"
            )

    failures = []
    try:
        display_path = path.relative_to(ROOT)
    except ValueError:
        display_path = path
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        direct_call = isinstance(node.func, ast.Name) and node.func.id in direct_names
        module_call = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "page"
            and _dotted_name(node.func.value) in module_names
        )
        if not (direct_call or module_call):
            continue
        keywords = {item.arg for item in node.keywords if item.arg is not None}
        if node.args or any(item.arg is None for item in node.keywords):
            failures.append(f"{display_path}:{node.lineno}: positional/**kwargs")
        missing = REQUIRED_KEYWORDS - keywords
        if missing:
            failures.append(
                f"{display_path}:{node.lineno}: missing {sorted(missing)}"
            )
        unknown = keywords - ALLOWED_KEYWORDS
        if unknown:
            failures.append(
                f"{display_path}:{node.lineno}: unknown {sorted(unknown)}"
            )
    return failures


def test_all_ui_shell_page_calls_use_canonical_keyword_contract():
    failures = []
    for path in (ROOT / "qrfacile_app").rglob("*.py"):
        failures.extend(_page_contract_violations(path))
    assert failures == []


def test_page_contract_scanner_handles_aliases_without_false_positives(tmp_path):
    sample = tmp_path / "sample.py"
    sample.write_text(
        "from qrfacile_app.ui_shell import page as shell_page\n"
        "def page(value): return value\n"
        "page('local')\n"
        "shell_page('legacy', 'subtitle', 'body')\n",
        encoding="utf-8",
    )
    failures = _page_contract_violations(sample)
    assert len(failures) == 2


def test_page_contract_scanner_handles_qualified_and_relative_imports(tmp_path):
    qualified = tmp_path / "qualified.py"
    qualified.write_text(
        "import qrfacile_app.ui_shell\n"
        "qrfacile_app.ui_shell.page('legacy', 'subtitle', 'body')\n",
        encoding="utf-8",
    )
    relative = tmp_path / "relative.py"
    relative.write_text(
        "from .ui_shell import page\n"
        "page('legacy', 'subtitle', 'body')\n",
        encoding="utf-8",
    )
    assert _page_contract_violations(qualified)
    assert _page_contract_violations(relative)
