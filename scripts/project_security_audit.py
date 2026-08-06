#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# These execute() calls interpolate only SQL fragments selected by application
# code. Values supplied by a request remain bound parameters. Keep this list
# exact (path + line is deliberately avoided so harmless edits do not invalidate
# the review) and cover every entry with regression tests.
REVIEWED_DYNAMIC_SQL = {
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

REVIEWED_READ_ONLY_GETS = {
    # Renders a confirmation form; the corresponding acceptance is POST-only.
    "qrfacile_app/invitation_acceptance_ui.py": '@router.' + 'get("/app/invite/studio/accept',
    # Renders invitation details and CSRF-protected POST forms only.
    "qrfacile_app/invitations_ui.py": '@router.' + 'get("/app/invite/{invite_type}/accept',
    # Lists existing acceptance evidence for administrators; it does not accept.
    "qrfacile_app/legal_acceptance_ui.py": '@router.' + 'get("/api/admin/compliance/legal-accept',
}


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    path: str
    line: int
    message: str


TEXT_SUFFIXES = {".py", ".html", ".js", ".sql", ".md"}
SKIP_PARTS = {".git", "venv", ".venv", "node_modules", "__pycache__", "_codex_reports"}


def _files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        yield path


def _line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def scan() -> list[Finding]:
    findings: list[Finding] = []
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")

        checks = [
            (
                "CRITICAL", "studio_publish_enabled",
                re.compile(r"can_publish\s*=\s*(?:TRUE|True|1)|name=[\"']can_publish[\"']", re.I),
                "Uno studio non deve poter ricevere il permesso di pubblicazione.",
            ),
            (
                "HIGH", "auto_verified_account",
                re.compile(r"email_verified\s*=\s*(?:1|TRUE)", re.I),
                "Verificare che gli account non siano marcati come email verificata senza prova della casella.",
            ),
            (
                "HIGH", "unsafe_state_change_get",
                re.compile(r"@router\.get\([^\n]*(?:delete|revoke|remove|publish|approve|accept)", re.I),
                "Operazione sensibile esposta tramite GET.",
            ),
            (
                "HIGH", "dynamic_sql_interpolation",
                re.compile(r"cur\.execute\(\s*f[\"']{3}", re.I),
                "SQL dinamico interpolato: verificare che nessun valore utente entri nella query.",
            ),
            (
                "MEDIUM", "raw_token_storage",
                re.compile(r"INSERT INTO\s+\w*invites[\s\S]{0,220}\btoken\b", re.I),
                "Token invito apparentemente conservato in chiaro; preferire token_hash.",
            ),
            (
                "MEDIUM", "broad_studio_access",
                re.compile(r"FROM\s+studio_clients[\s\S]{0,260}can_view\s*=\s*TRUE", re.I),
                "Controllo studio basato solo sul collegamento generale: verificare anche label_collaborators.",
            ),
        ]

        for severity, code, pattern, message in checks:
            for match in pattern.finditer(text):
                # Eccezioni intenzionali nel servizio centrale e nelle migrazioni di hardening.
                if code == "studio_publish_enabled" and rel in {
                    "qrfacile_app/services/collaboration_access.py",
                    "sql/2026_collaboration_access_hardening.sql",
                    "tests/test_collaboration_access_hardening.py",
                }:
                    continue
                if code == "broad_studio_access" and rel == "qrfacile_app/services/collaboration_access.py":
                    continue
                if code == "dynamic_sql_interpolation" and rel in REVIEWED_DYNAMIC_SQL:
                    remainder = text[match.end():]
                    closing = re.search(r'"""|\'\'\'', remainder)
                    statement = remainder[:closing.start()] if closing else ""
                    interpolated = set(re.findall(r"\{([A-Za-z_][A-Za-z0-9_]*)\}", statement))
                    if interpolated and interpolated <= REVIEWED_DYNAMIC_SQL[rel]:
                        continue
                if code == "unsafe_state_change_get" and rel in REVIEWED_READ_ONLY_GETS:
                    route = REVIEWED_READ_ONLY_GETS[rel]
                    if route in match.group(0):
                        continue
                if rel == "tests/test_security_regressions.py" and code in {
                    "unsafe_state_change_get",
                    "auto_verified_account",
                }:
                    continue
                # Temporary migration fixture inserts an explicit SQL NULL, not
                # a plaintext invitation token.
                if code == "raw_token_storage" and rel == "tests/test_staging_reconciliation_database.py":
                    continue
                # The service sets this flag only after locking and validating a
                # hashed, unused, unrevoked and unexpired verification token.
                if code == "auto_verified_account" and rel == "qrfacile_app/services/email_verification.py":
                    continue
                # Tests assert the verified transition; they do not create users.
                if code == "auto_verified_account" and rel == "tests/test_email_verification.py":
                    continue
                findings.append(Finding(
                    severity=severity,
                    code=code,
                    path=rel,
                    line=_line_number(text, match.start()),
                    message=message,
                ))

    findings.sort(key=lambda item: ({"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}.get(item.severity, 9), item.path, item.line))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit statico sicurezza e autorizzazioni QRFacile")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--fail-on", choices=("critical", "high", "medium", "never"), default="critical")
    args = parser.parse_args()

    findings = scan()
    if args.as_json:
        print(json.dumps({"findings": [asdict(item) for item in findings], "count": len(findings)}, ensure_ascii=False, indent=2))
    else:
        print(f"QRFacile project security audit: {len(findings)} finding(s)")
        for item in findings:
            print(f"{item.severity:8} {item.code:28} {item.path}:{item.line} - {item.message}")

    thresholds = {"critical": {"CRITICAL"}, "high": {"CRITICAL", "HIGH"}, "medium": {"CRITICAL", "HIGH", "MEDIUM"}, "never": set()}
    return 1 if any(item.severity in thresholds[args.fail_on] for item in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
