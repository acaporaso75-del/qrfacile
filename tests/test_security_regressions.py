import ast
import re
import subprocess
import sys
from pathlib import Path

from scripts.project_security_audit import REVIEWED_DYNAMIC_SQL, scan


ROOT = Path(__file__).resolve().parents[1]


def test_tracked_sources_pass_detect_secrets():
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    files = [
        item.decode()
        for item in tracked.split(b"\0")
        if item and (ROOT / item.decode()).is_file()
    ]
    hook = Path(sys.executable).with_name("detect-secrets-hook")
    result = subprocess.run(
        [hook, *files],
        cwd=ROOT,
        capture_output=True,
    )
    assert result.returncode == 0, "detect-secrets found a tracked hardcoded credential"


def test_no_literal_assignments_to_credential_names():
    credential_name = re.compile(r"(password|passwd|token|secret|api_key|private_key)", re.I)
    violations = []
    for relative in subprocess.check_output(
        ["git", "ls-files", "*.py"], cwd=ROOT, text=True
    ).splitlines():
        path = ROOT / relative
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source, filename=relative)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                continue
            if "pragma: allowlist secret" in lines[node.lineno - 1]:
                continue
            for target in targets:
                if (
                    isinstance(target, ast.Name)
                    and credential_name.search(target.id)
                    and not target.id.endswith("_ENV")
                ):
                    violations.append(f"{relative}:{node.lineno}:{target.id}")
    assert not violations, "literal credentials: " + ", ".join(violations)


def test_sensitive_actions_are_not_exposed_by_get():
    findings = [item for item in scan() if item.code == "unsafe_state_change_get"]
    assert not findings
    source = (ROOT / "qrfacile_app" / "studio_settings_ui.py").read_text(encoding="utf-8")
    assert '@router.get("/app/invite/studio/accept/{token}"' not in source
    assert '@router.post("/app/invite/studio/accept/{token}")' in source


def test_verified_accounts_require_a_valid_one_time_token():
    source = (ROOT / "qrfacile_app" / "services" / "email_verification.py").read_text(encoding="utf-8")
    lock = source.index("FOR UPDATE")
    reject = source.index('if not row or row.get("used_at") or row.get("revoked_at")')
    expiry = source.index('if row["expires_at"] < datetime.now(timezone.utc)')
    verify = source.index("UPDATE users SET email_verified=TRUE")
    consume = source.index("UPDATE email_verification_tokens SET used_at=now()")
    assert lock < reject < expiry < verify < consume
    assert "WHERE token_hash=%s" in source


def test_reviewed_dynamic_sql_uses_internal_fragments_and_bound_values():
    expected = {
        "qrfacile_app/admin_legacy_ui.py": {"where"},
        "qrfacile_app/admin_override_requests_ui.py": {"where"},
        "qrfacile_app/auth_core.py": {"col"},
        "qrfacile_app/bulk_tools.py": {"where"},
        "qrfacile_app/compliance_incidents_ui.py": {"where"},
        "qrfacile_app/dashboard_ui.py": {"pending_join", "pending_select", "where"},
        "qrfacile_app/privacy_requests_ui.py": {"where"},
        "qrfacile_app/public.py": {"all_col", "ing_col"},
        "qrfacile_app/services/collaboration_access.py": {"required_column"},
    }
    assert REVIEWED_DYNAMIC_SQL == expected

    auth = (ROOT / "qrfacile_app" / "auth_core.py").read_text(encoding="utf-8")
    assert 'col = "can_view"' in auth
    assert 'col = "can_edit"' in auth
    assert 'col = "can_create"' in auth
    assert "AND {col}=TRUE" in auth

    collaboration = (ROOT / "qrfacile_app" / "services" / "collaboration_access.py").read_text(encoding="utf-8")
    assert 'required_column = "lc.can_view" if permission == "view" else "lc.can_edit"' in collaboration

    public = (ROOT / "qrfacile_app" / "public.py").read_text(encoding="utf-8")
    assert '_pick_first_col(cur, "ingredients_master", ["name", "title", "label", "text", "description"])' in public
    assert '_pick_first_col(cur, "allergens_master", ["name", "title", "label", "text", "description"])' in public

    # All request-derived filters in the reviewed queries are still parameters.
    for relative in expected:
        source = (ROOT / relative).read_text(encoding="utf-8")
        assert "%s" in source
