#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qrfacile_app.runtime_config import load_runtime_config
from qrfacile_app.services.transactional_email import load_smtp_config
from scripts.check_accessibility_acceptance import validate_accessibility_acceptance
from scripts.check_production_approvals import approved_release, evidence_only_changes, validate_approvals
from scripts.check_restore_acceptance import validate_restore_acceptance
from scripts.run_operational_monitor import load_alert_recipient


FULL_GIT_SHA = re.compile(r"[0-9a-f]{40}")
PRODUCTION_ORIGINS = {"https://qrfacile.it", "https://www.qrfacile.it"}
REQUIRED_MIGRATIONS = (
    "2026_legal_ai_compliance.sql",
    "2026_legal_acceptance_constraints.sql",
    "2026_privacy_requests.sql",
    "2026_ai_system_registry.sql",
    "2026_wine_compliance_replays.sql",
    "2026_collaboration_access_hardening.sql",
    "2026_invitation_lifecycle.sql",
    "2026_invitation_acceptance_hardening.sql",
    "2026_email_verification.sql",
    "2026_production_qr_wines_qr_item_unique.sql",
    "2026_unified_invitations.sql",
    "2026_orders_payment_environment.sql",
    "2026_sell_ready_legal_documents.sql",
    "2026_annual_wine_packages.sql",
    "2026_winery_fiscal_profile.sql",
    "2026_email_verification_enforcement.sql",
    "2026_login_rate_limit.sql",
    "2026_terms_single_reference_qr.sql",
    "2026_paypal_webhook_events.sql",
)


def _git_head(candidate_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(candidate_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip().lower()


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _verified_backup_files(path: Path) -> int:
    manifest = path / "SHA256SUMS"
    if not manifest.is_file():
        raise ValueError("manifest assente")
    entries = 0
    for raw_line in manifest.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{64})\s+[ *](.+)", line)
        if not match:
            raise ValueError("manifest non valido")
        expected, relative = match.groups()
        item = (path / relative).resolve(strict=False)
        if path.resolve() not in item.parents or not item.is_file() or item.is_symlink():
            raise ValueError("percorso backup non valido")
        digest = hashlib.sha256()
        with item.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != expected.lower():
            raise ValueError("checksum non valido")
        entries += 1
    return entries


def _backup_age_seconds(path: Path) -> float | None:
    manifest = path / "SHA256SUMS"
    if not manifest.is_file():
        return None
    return time.time() - manifest.stat().st_mtime


def evaluate_preflight(
    *,
    source: dict[str, str],
    config,
    candidate_root: Path,
    backup_path: Path,
    rollback_path: Path,
    expected_environment: str,
    expected_release: str,
    expected_paypal_mode: str,
    git_head: str,
    free_bytes: int,
    min_free_bytes: int,
    backup_age_seconds: float | None = 0.0,
    max_backup_age_seconds: float = 24 * 60 * 60,
    approval_errors: list[str] | None = None,
    accessibility_errors: list[str] | None = None,
    restore_errors: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if approval_errors:
        errors.append("approvazioni produzione incomplete o incoerenti")
    if accessibility_errors:
        errors.append("accettazione accessibilità incompleta o incoerente")
    if restore_errors:
        errors.append("accettazione restore incompleta o incoerente")
    if not config.environment_explicit:
        errors.append("APP_ENV deve essere dichiarato esplicitamente")
    if config.environment != expected_environment:
        errors.append("ambiente runtime diverso da quello atteso")
    if (source.get("QRFACILE_RELEASE_SHA") or "").strip().lower() != expected_release:
        errors.append("QRFACILE_RELEASE_SHA non coincide con il candidato")
    if git_head != expected_release:
        errors.append("HEAD del checkout candidato non coincide con lo SHA atteso")

    paypal_mode = (source.get("PAYPAL_MODE") or "").strip().lower()
    if paypal_mode != expected_paypal_mode:
        errors.append("PAYPAL_MODE non coincide con la modalità autorizzata")
    paypal_webhook_fields = ("PAYPAL_CLIENT_ID", "PAYPAL_SECRET", "PAYPAL_WEBHOOK_ID")
    if any(not (source.get(name) or "").strip() for name in paypal_webhook_fields):
        errors.append("configurazione PayPal webhook incompleta")
    if load_smtp_config(source) is None:
        errors.append("configurazione SMTP transazionale incompleta")
    if load_alert_recipient(source) is None:
        errors.append("destinatario alert operativo mancante o non valido")

    runtime_directories = (
        config.app_root,
        config.uploads_dir,
        config.templates_dir,
        config.static_dir,
    )
    if any(not path.is_dir() for path in runtime_directories):
        errors.append("directory runtime o persistenti non disponibili")
    if not config.database_host:
        errors.append("host database non configurato")

    if expected_environment == "production":
        if _origin(config.app_base_url) not in PRODUCTION_ORIGINS:
            errors.append("APP_BASE_URL non usa un'origine produttiva QRFacile")
        if config.database_name != "qrfacile_db":
            errors.append("database produttivo inatteso")
        if config.database_user != "qrfacile_user":
            errors.append("utente database produttivo inatteso")

    required_candidate = (
        candidate_root / "main.py",
        candidate_root / "requirements.txt",
        candidate_root / "qrfacile_app" / "__init__.py",
        candidate_root / "templates",
        candidate_root / "static",
        candidate_root / "sql",
    )
    if any(not path.exists() for path in required_candidate):
        errors.append("checkout candidato incompleto")
    missing_migrations = [
        name for name in REQUIRED_MIGRATIONS if not (candidate_root / "sql" / name).is_file()
    ]
    if missing_migrations:
        errors.append("set di migrazioni produttive incompleto")

    if not rollback_path.is_dir() or rollback_path.resolve() == candidate_root.resolve():
        errors.append("percorso rollback assente o coincidente con il candidato")
    elif not (rollback_path / "main.py").is_file():
        errors.append("percorso rollback non contiene una release QRFacile")

    if not backup_path.is_dir():
        errors.append("backup pre-deploy non disponibile")
    else:
        try:
            if _verified_backup_files(backup_path) < 2:
                errors.append("backup pre-deploy incompleto o non verificabile")
            elif (
                backup_age_seconds is None
                or backup_age_seconds < -300
                or backup_age_seconds > max_backup_age_seconds
            ):
                errors.append("backup pre-deploy non recente")
        except (OSError, UnicodeError, ValueError):
            errors.append("backup pre-deploy incompleto o non verificabile")

    if free_bytes < min_free_bytes:
        errors.append("spazio disco libero inferiore alla soglia")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preflight locale fail-closed per una release QRFacile, senza modifiche"
    )
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--backup-path", type=Path, required=True)
    parser.add_argument("--rollback-path", type=Path, required=True)
    parser.add_argument("--expected-environment", choices=("staging", "production"), required=True)
    parser.add_argument("--expected-release", required=True)
    parser.add_argument("--expected-paypal-mode", choices=("sandbox", "live"), required=True)
    parser.add_argument("--approvals-path", type=Path, required=True)
    parser.add_argument("--accessibility-path", type=Path, required=True)
    parser.add_argument("--restore-acceptance-path", type=Path, required=True)
    parser.add_argument("--expected-pr", type=int, required=True)
    parser.add_argument("--min-free-gb", type=float, default=2.0)
    parser.add_argument("--max-backup-age-hours", type=float, default=24.0)
    args = parser.parse_args(argv)

    expected_release = args.expected_release.strip().lower()
    if not FULL_GIT_SHA.fullmatch(expected_release):
        parser.error("--expected-release deve essere uno SHA Git completo")
    if args.min_free_gb <= 0:
        parser.error("--min-free-gb deve essere maggiore di zero")
    if args.max_backup_age_hours <= 0:
        parser.error("--max-backup-age-hours deve essere maggiore di zero")
    if args.expected_pr <= 0:
        parser.error("--expected-pr deve essere positivo")

    candidate_root = args.candidate_root.resolve()
    backup_path = args.backup_path.resolve()
    rollback_path = args.rollback_path.resolve()
    try:
        config = load_runtime_config(os.environ)
        git_head = _git_head(candidate_root)
        free_bytes = shutil.disk_usage(candidate_root).free
        approvals_text = args.approvals_path.read_text(encoding="utf-8")
        accessibility_text = args.accessibility_path.read_text(encoding="utf-8")
        restore_text = args.restore_acceptance_path.read_text(encoding="utf-8")
        approved_sha = approved_release(approvals_text)
        approval_paths = (
            evidence_only_changes(candidate_root, approved_sha, expected_release)
            if approved_sha and approved_sha != expected_release
            else set()
        )
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(f"RELEASE_PREFLIGHT_ERROR {type(exc).__name__}", file=sys.stderr)
        return 2

    errors = evaluate_preflight(
        source=dict(os.environ),
        config=config,
        candidate_root=candidate_root,
        backup_path=backup_path,
        rollback_path=rollback_path,
        expected_environment=args.expected_environment,
        expected_release=expected_release,
        expected_paypal_mode=args.expected_paypal_mode,
        git_head=git_head,
        free_bytes=free_bytes,
        min_free_bytes=int(args.min_free_gb * 1024**3),
        backup_age_seconds=_backup_age_seconds(backup_path),
        max_backup_age_seconds=args.max_backup_age_hours * 60 * 60,
        approval_errors=validate_approvals(
            approvals_text,
            expected_release=expected_release,
            expected_pr=args.expected_pr,
            post_approval_paths=approval_paths,
        ),
        accessibility_errors=validate_accessibility_acceptance(
            accessibility_text,
            expected_release=expected_release,
            expected_environment=args.expected_environment,
        ),
        restore_errors=validate_restore_acceptance(
            restore_text,
            expected_release=expected_release,
            expected_environment=args.expected_environment,
            expected_backup_path=backup_path,
        ),
    )
    if errors:
        for error in errors:
            print(f"RELEASE_PREFLIGHT_MISMATCH {error}", file=sys.stderr)
        return 1
    print(
        "RELEASE_PREFLIGHT_OK "
        f"environment={args.expected_environment} release={expected_release} "
        f"paypal_mode={args.expected_paypal_mode} migrations={len(REQUIRED_MIGRATIONS)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
