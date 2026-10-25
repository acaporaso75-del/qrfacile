import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_sensitive_admin_and_compliance_mutations_require_csrf_or_same_origin():
    expected_minimum = {
        "admin_credits_ui.py": 1,
        "admin_home_ui.py": 1,
        "admin_override_requests_ui.py": 2,
        "admin_payouts_ui.py": 2,
        "ai_registry_ui.py": 1,
        "ai_review_ui.py": 1,
        "compliance_incidents_ui.py": 2,
        "compliance_ui.py": 1,
        "privacy_requests_ui.py": 1,
    }
    for filename, minimum in expected_minimum.items():
        source = (ROOT / "qrfacile_app" / filename).read_text(encoding="utf-8")
        assert "from qrfacile_app.csrf_core import require_csrf_or_same_origin" in source
        assert source.count("require_csrf_or_same_origin(request)") >= minimum


def test_every_authenticated_mutation_has_an_explicit_csrf_or_origin_gate():
    public_mutations = {
        "/login", "/forgot-password", "/reset-password",
        "/register-studio", "/register-winery",
    }
    missing = []
    for path in sorted((ROOT / "qrfacile_app").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        lines = source.splitlines()
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            routes = []
            for decorator in node.decorator_list:
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr in {"post", "put", "patch", "delete"}
                    and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                ):
                    routes.append(str(decorator.args[0].value))
            protected_routes = [route for route in routes if route not in public_mutations]
            if not protected_routes:
                continue
            body = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            if not any(gate in body for gate in (
                "require_csrf(", "require_csrf_or_same_origin(", "_same_origin("
            )):
                missing.extend(f"{path.name}:{node.name}:{route}" for route in protected_routes)
    assert missing == []
