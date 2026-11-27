from __future__ import annotations

import hashlib
from pathlib import Path
from runpy import run_path

import pytest

from qrfacile_app.runtime_config import load_runtime_config
from scripts import check_release_preflight


SHA = "a" * 40


def _production_source(root: Path) -> dict[str, str]:
    for directory in (root, root / "uploads", root / "templates", root / "static"):
        directory.mkdir(parents=True, exist_ok=True)
    return {
        "APP_ENV": "production",
        "APP_ROOT": str(root),
        "UPLOADS_DIR": str(root / "uploads"),
        "TEMPLATES_DIR": str(root / "templates"),
        "STATIC_DIR": str(root / "static"),
        "APP_BASE_URL": "https://www.qrfacile.it",
        "DATABASE_URL": "postgresql://qrfacile_user:test-only@db/qrfacile_db",  # pragma: allowlist secret
        "CSRF_SECRET": "test-only-csrf-secret",  # pragma: allowlist secret
        "PAYPAL_MODE": "sandbox",
        "PAYPAL_CLIENT_ID": "test-only-client-id",
        "PAYPAL_SECRET": "test-only-paypal-secret",  # pragma: allowlist secret
        "PAYPAL_WEBHOOK_ID": "test-only-webhook-id",
        "QRFACILE_RELEASE_SHA": SHA,
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": "465",
        "SMTP_USER": "mailer@example.test",
        "SMTP_PASS": "test-only",  # pragma: allowlist secret
        "SMTP_FROM": "QRFacile <mailer@example.test>",
        "QRFACILE_OPERATIONAL_ALERT_TO": "ops@example.test",
    }


def _release_tree(root: Path) -> None:
    (root / "qrfacile_app").mkdir(parents=True)
    (root / "templates").mkdir()
    (root / "static").mkdir()
    (root / "sql").mkdir()
    for relative in ("main.py", "requirements.txt", "qrfacile_app/__init__.py"):
        (root / relative).write_text("# test\n", encoding="utf-8")
    for name in check_release_preflight.REQUIRED_MIGRATIONS:
        (root / "sql" / name).write_text("BEGIN; COMMIT;\n", encoding="utf-8")


def _verified_backup(root: Path) -> None:
    root.mkdir()
    files = {
        "database.dump": b"database",
        "filesystem.tar": b"filesystem",
    }
    manifest = []
    for name, content in files.items():
        (root / name).write_bytes(content)
        manifest.append(f"{hashlib.sha256(content).hexdigest()}  {name}")
    (root / "SHA256SUMS").write_text("\n".join(manifest) + "\n", encoding="utf-8")


def test_backup_verification_rejects_checksum_mismatch_and_path_escape(tmp_path):
    backup = tmp_path / "backup"
    _verified_backup(backup)
    (backup / "database.dump").write_bytes(b"tampered")
    with pytest.raises(ValueError):
        check_release_preflight._verified_backup_files(backup)

    outside = tmp_path / "outside.dump"
    outside.write_bytes(b"outside")
    digest = hashlib.sha256(outside.read_bytes()).hexdigest()
    (backup / "SHA256SUMS").write_text(f"{digest}  ../outside.dump\n", encoding="utf-8")
    with pytest.raises(ValueError):
        check_release_preflight._verified_backup_files(backup)


def test_preflight_rejects_stale_or_future_dated_backup(tmp_path):
    runtime_root = tmp_path / "runtime"
    candidate = tmp_path / "candidate"
    rollback = tmp_path / "rollback"
    backup = tmp_path / "backup"
    _release_tree(candidate)
    _release_tree(rollback)
    _verified_backup(backup)
    source = _production_source(runtime_root)

    common = dict(
        source=source,
        config=load_runtime_config(source),
        candidate_root=candidate,
        backup_path=backup,
        rollback_path=rollback,
        expected_environment="production",
        expected_release=SHA,
        expected_paypal_mode="sandbox",
        git_head=SHA,
        free_bytes=5 * 1024**3,
        min_free_bytes=2 * 1024**3,
        max_backup_age_seconds=24 * 60 * 60,
    )
    assert check_release_preflight.evaluate_preflight(
        **common,
        backup_age_seconds=25 * 60 * 60,
    ) == ["backup pre-deploy non recente"]
    assert check_release_preflight.evaluate_preflight(
        **common,
        backup_age_seconds=-301,
    ) == ["backup pre-deploy non recente"]

def test_preflight_accepts_complete_production_candidate(tmp_path):
    runtime_root = tmp_path / "runtime"
    candidate = tmp_path / "candidate"
    rollback = tmp_path / "rollback"
    backup = tmp_path / "backup"
    _release_tree(candidate)
    _release_tree(rollback)
    _verified_backup(backup)
    source = _production_source(runtime_root)

    errors = check_release_preflight.evaluate_preflight(
        source=source,
        config=load_runtime_config(source),
        candidate_root=candidate,
        backup_path=backup,
        rollback_path=rollback,
        expected_environment="production",
        expected_release=SHA,
        expected_paypal_mode="sandbox",
        git_head=SHA,
        free_bytes=5 * 1024**3,
        min_free_bytes=2 * 1024**3,
    )

    assert errors == []


def test_preflight_fails_closed_without_identity_backup_rollback_and_capacity(tmp_path):
    runtime_root = tmp_path / "runtime"
    candidate = tmp_path / "candidate"
    _release_tree(candidate)
    source = _production_source(runtime_root)
    source["QRFACILE_RELEASE_SHA"] = "b" * 40
    source["PAYPAL_MODE"] = "live"
    source.pop("PAYPAL_WEBHOOK_ID")
    source.pop("SMTP_PASS")
    source["QRFACILE_OPERATIONAL_ALERT_TO"] = "Ops <ops@example.test>"

    errors = check_release_preflight.evaluate_preflight(
        source=source,
        config=load_runtime_config({**source, "PAYPAL_CLIENT_ID": "id", "PAYPAL_SECRET": "secret", "PAYPAL_WEBHOOK_ID": "webhook"}),  # pragma: allowlist secret
        candidate_root=candidate,
        backup_path=tmp_path / "missing-backup",
        rollback_path=candidate,
        expected_environment="production",
        expected_release=SHA,
        expected_paypal_mode="sandbox",
        git_head="c" * 40,
        free_bytes=1,
        min_free_bytes=2 * 1024**3,
    )

    assert "QRFACILE_RELEASE_SHA non coincide con il candidato" in errors
    assert "HEAD del checkout candidato non coincide con lo SHA atteso" in errors
    assert "PAYPAL_MODE non coincide con la modalità autorizzata" in errors
    assert "configurazione PayPal webhook incompleta" in errors
    assert "configurazione SMTP transazionale incompleta" in errors
    assert "destinatario alert operativo mancante o non valido" in errors
    assert "percorso rollback assente o coincidente con il candidato" in errors
    assert "backup pre-deploy non disponibile" in errors
    assert "spazio disco libero inferiore alla soglia" in errors


def test_preflight_blocks_incomplete_external_approvals(tmp_path):
    runtime_root = tmp_path / "runtime"
    candidate = tmp_path / "candidate"
    rollback = tmp_path / "rollback"
    backup = tmp_path / "backup"
    _release_tree(candidate)
    _release_tree(rollback)
    _verified_backup(backup)
    source = _production_source(runtime_root)

    errors = check_release_preflight.evaluate_preflight(
        source=source,
        config=load_runtime_config(source),
        candidate_root=candidate,
        backup_path=backup,
        rollback_path=rollback,
        expected_environment="production",
        expected_release=SHA,
        expected_paypal_mode="sandbox",
        git_head=SHA,
        free_bytes=5 * 1024**3,
        min_free_bytes=2 * 1024**3,
        approval_errors=["campo esterno mancante"],
    )

    assert errors == ["approvazioni produzione incomplete o incoerenti"]


def test_preflight_blocks_incomplete_accessibility_acceptance(tmp_path):
    runtime_root = tmp_path / "runtime"
    candidate = tmp_path / "candidate"
    rollback = tmp_path / "rollback"
    backup = tmp_path / "backup"
    _release_tree(candidate)
    _release_tree(rollback)
    _verified_backup(backup)
    source = _production_source(runtime_root)

    errors = check_release_preflight.evaluate_preflight(
        source=source,
        config=load_runtime_config(source),
        candidate_root=candidate,
        backup_path=backup,
        rollback_path=rollback,
        expected_environment="production",
        expected_release=SHA,
        expected_paypal_mode="sandbox",
        git_head=SHA,
        free_bytes=5 * 1024**3,
        min_free_bytes=2 * 1024**3,
        accessibility_errors=["percorso A01 non verificato"],
    )

    assert errors == ["accettazione accessibilità incompleta o incoerente"]


def test_preflight_blocks_incomplete_restore_acceptance(tmp_path):
    runtime_root = tmp_path / "runtime"
    candidate = tmp_path / "candidate"
    rollback = tmp_path / "rollback"
    backup = tmp_path / "backup"
    _release_tree(candidate)
    _release_tree(rollback)
    _verified_backup(backup)
    source = _production_source(runtime_root)

    errors = check_release_preflight.evaluate_preflight(
        source=source,
        config=load_runtime_config(source),
        candidate_root=candidate,
        backup_path=backup,
        rollback_path=rollback,
        expected_environment="production",
        expected_release=SHA,
        expected_paypal_mode="sandbox",
        git_head=SHA,
        free_bytes=5 * 1024**3,
        min_free_bytes=2 * 1024**3,
        restore_errors=["restore non verificato"],
    )

    assert errors == ["accettazione restore incompleta o incoerente"]


def test_preflight_blocks_incomplete_operational_acceptance(tmp_path):
    runtime_root = tmp_path / "runtime"
    candidate = tmp_path / "candidate"
    rollback = tmp_path / "rollback"
    backup = tmp_path / "backup"
    _release_tree(candidate)
    _release_tree(rollback)
    _verified_backup(backup)
    source = _production_source(runtime_root)

    errors = check_release_preflight.evaluate_preflight(
        source=source,
        config=load_runtime_config(source),
        candidate_root=candidate,
        backup_path=backup,
        rollback_path=rollback,
        expected_environment="production",
        expected_release=SHA,
        expected_paypal_mode="sandbox",
        git_head=SHA,
        free_bytes=5 * 1024**3,
        min_free_bytes=2 * 1024**3,
        operational_errors=["consegna non verificata"],
    )

    assert errors == ["accettazione SMTP/alert incompleta o incoerente"]


def test_preflight_blocks_incomplete_paypal_sandbox_acceptance(tmp_path):
    runtime_root = tmp_path / "runtime"
    candidate = tmp_path / "candidate"
    rollback = tmp_path / "rollback"
    backup = tmp_path / "backup"
    _release_tree(candidate)
    _release_tree(rollback)
    _verified_backup(backup)
    source = _production_source(runtime_root)

    errors = check_release_preflight.evaluate_preflight(
        source=source,
        config=load_runtime_config(source),
        candidate_root=candidate,
        backup_path=backup,
        rollback_path=rollback,
        expected_environment="production",
        expected_release=SHA,
        expected_paypal_mode="sandbox",
        git_head=SHA,
        free_bytes=5 * 1024**3,
        min_free_bytes=2 * 1024**3,
        paypal_sandbox_errors=["firma non verificata"],
    )

    assert errors == ["accettazione webhook PayPal Sandbox incompleta o incoerente"]


def test_preflight_rejects_missing_runtime_directory_without_exposing_database_url(tmp_path):
    runtime_root = tmp_path / "runtime"
    candidate = tmp_path / "candidate"
    rollback = tmp_path / "rollback"
    backup = tmp_path / "backup"
    _release_tree(candidate)
    _release_tree(rollback)
    _verified_backup(backup)
    source = _production_source(runtime_root)
    (runtime_root / "uploads").rmdir()

    errors = check_release_preflight.evaluate_preflight(
        source=source,
        config=load_runtime_config(source),
        candidate_root=candidate,
        backup_path=backup,
        rollback_path=rollback,
        expected_environment="production",
        expected_release=SHA,
        expected_paypal_mode="sandbox",
        git_head=SHA,
        free_bytes=5 * 1024**3,
        min_free_bytes=2 * 1024**3,
    )

    assert errors == ["directory runtime o persistenti non disponibili"]
    assert "test-only" not in " ".join(errors)


def _completed_acceptance_documents(backup: Path) -> dict[str, str]:
    def fixture(test_file: str, name: str, *args) -> str:
        return run_path(str(Path(__file__).with_name(f"test_{test_file}.py")))[name](*args)

    staging = "[x] staging  [ ] produzione"
    production = "[ ] staging  [x] produzione"
    return {
        "approvals": fixture("production_approvals", "_complete_document"),
        "accessibility": fixture("accessibility_acceptance", "_complete_document")
        .replace(production, staging)
        .replace("https://www.qrfacile.it", "https://staging.example.test"),
        "operational-acceptance": fixture("operational_acceptance", "_complete")
        .replace(staging, production)
        .replace("https://staging.example.test", "https://www.qrfacile.it"),
        "paypal-sandbox-acceptance": fixture("paypal_sandbox_acceptance", "_complete"),
        "restore-acceptance": fixture("restore_acceptance", "_complete_document", backup),
    }


@pytest.mark.parametrize(("document", "before", "after", "error"), [
    (None, "", "", None),
    ("accessibility", "[x] staging  [ ] produzione", "[ ] staging  [x] produzione",
     "accettazione accessibilità incompleta o incoerente"),
    ("paypal-sandbox-acceptance", "[x] staging  [ ] produzione", "[ ] staging  [x] produzione",
     "accettazione webhook PayPal Sandbox incompleta o incoerente"),
    ("paypal-sandbox-acceptance", SHA, "b" * 40,
     "accettazione webhook PayPal Sandbox incompleta o incoerente"),
    ("operational-acceptance", "[ ] staging  [x] produzione", "[x] staging  [ ] produzione",
     "accettazione SMTP/alert incompleta o incoerente"),
    ("restore-acceptance", "[ ] staging  [x] produzione", "[x] staging  [ ] produzione",
     "accettazione restore incompleta o incoerente"),
    ("approvals", "Esito finale: [x] GO  [ ] NO-GO", "Esito finale: [ ] GO  [x] NO-GO",
     "approvazioni produzione incomplete o incoerenti"),
])
def test_production_preflight_validates_rehearsals_without_relaxing_release_gates(
    tmp_path, monkeypatch, capsys, document, before, after, error
):
    candidate = tmp_path / "candidate"
    rollback = tmp_path / "rollback"
    backup = tmp_path / "backup"
    _release_tree(candidate)
    _release_tree(rollback)
    _verified_backup(backup)
    for name, value in _production_source(tmp_path / "runtime").items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(check_release_preflight, "_git_head", lambda _root: SHA)

    documents = _completed_acceptance_documents(backup)
    if document is not None:
        assert before in documents[document]
        documents[document] = documents[document].replace(before, after)
    args = [
        "--candidate-root", str(candidate),
        "--backup-path", str(backup),
        "--rollback-path", str(rollback),
        "--expected-environment", "production",
        "--expected-release", SHA,
        "--expected-paypal-mode", "sandbox",
        "--expected-pr", "12",
        "--min-free-gb", "0.001",
    ]
    for name, content in documents.items():
        path = tmp_path / f"{name}.md"
        path.write_text(content, encoding="utf-8")
        args.extend([f"--{name}-path", str(path)])

    exit_code = check_release_preflight.main(args)
    output = capsys.readouterr()
    if error is None:
        assert exit_code == 0, output.err
        assert f"RELEASE_PREFLIGHT_OK environment=production release={SHA}" in output.out
    else:
        assert exit_code == 1
        assert output.err.splitlines() == [f"RELEASE_PREFLIGHT_MISMATCH {error}"]
        assert "RELEASE_PREFLIGHT_OK" not in output.out


def test_preflight_never_reports_sensitive_configuration(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        check_release_preflight,
        "load_runtime_config",
        lambda _source: (_ for _ in ()).throw(RuntimeError("configurazione non valida")),
    )
    assert check_release_preflight.main([
        "--candidate-root", str(tmp_path),
        "--backup-path", str(tmp_path),
        "--rollback-path", str(tmp_path),
        "--expected-environment", "production",
        "--expected-release", SHA,
        "--expected-paypal-mode", "sandbox",
        "--approvals-path", str(tmp_path / "missing-approvals.md"),
        "--accessibility-path", str(tmp_path / "missing-accessibility.md"),
        "--operational-acceptance-path", str(tmp_path / "missing-operational.md"),
        "--paypal-sandbox-acceptance-path", str(tmp_path / "missing-paypal-sandbox.md"),
        "--restore-acceptance-path", str(tmp_path / "missing-restore.md"),
        "--expected-pr", "12",
    ]) == 2
    output = capsys.readouterr()
    assert "RuntimeError" in output.err
    assert "configurazione non valida" not in output.err
