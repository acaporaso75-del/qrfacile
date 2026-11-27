import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, Request

from qrfacile_app import paypal_ui
from qrfacile_app.services import invoice_handoff


ROOT = Path(__file__).resolve().parents[1]


def _event(*, amount="120.78", currency="EUR", order_id="PP-77"):
    return {
        "id": "WH-1",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAP-1",
            "status": "COMPLETED",
            "amount": {"currency_code": currency, "value": amount},
            "supplementary_data": {"related_ids": {"order_id": order_id}},
        },
    }


def _order():
    return {
        "id": 77,
        "paypal_order_id": "PP-77",
        "amount_cents": 12078,
        "currency": "EUR",
    }


def test_webhook_capture_identity_requires_exact_order_amount_and_currency():
    assert paypal_ui._webhook_capture_identity(_event(), _order()) == ("PP-77", "CAP-1")
    for changes in (
        {"amount": "99.00"},
        {"currency": "USD"},
        {"order_id": "PP-OTHER"},
    ):
        with pytest.raises(RuntimeError, match="non coerente"):
            paypal_ui._webhook_capture_identity(_event(**changes), _order())


class _Response:
    status_code = 200

    @staticmethod
    def json():
        return {"verification_status": "SUCCESS"}


def _headers(cert_url="https://api.sandbox.paypal.com/v1/notifications/certs/CERT-1"):
    return {
        "paypal-transmission-id": "T-1",
        "paypal-transmission-time": "2026-10-29T12:00:00Z",
        "paypal-cert-url": cert_url,
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-transmission-sig": "signature-value",
    }


def _sandbox(monkeypatch):
    monkeypatch.setattr(paypal_ui, "PAYPAL_MODE", "sandbox")
    monkeypatch.setattr(paypal_ui, "PAYPAL_BASE", "https://api-m.sandbox.paypal.com")
    monkeypatch.setattr(paypal_ui, "PAYPAL_WEBHOOK_ID", "WH-CONFIGURED")
    monkeypatch.setattr(paypal_ui, "_paypal_token", lambda: "not-logged-token")


def _post_webhook(event, headers):
    body = json.dumps(event).encode("utf-8")
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/paypal/webhook",
        "headers": [(key.encode("ascii"), value.encode("ascii")) for key, value in headers.items()],
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def invoke():
        response = await paypal_ui.paypal_webhook(Request(scope, receive))
        if response.background is not None:
            await response.background()
        return response

    return asyncio.run(invoke())


@pytest.mark.parametrize("cert_url", [
    "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-1",
    "https://api-m.sandbox.paypal.com/v1/notifications/certs/CERT-1",
    "https://api.sandbox.paypal.com:443/v1/notifications/certs/CERT-1",
])
def test_signature_verification_posts_required_fields_to_paypal(monkeypatch, cert_url):
    posted = {}
    _sandbox(monkeypatch)

    def fake_post(url, **kwargs):
        posted.update({"url": url, **kwargs})
        return _Response()

    monkeypatch.setattr(paypal_ui, "_paypal_post", fake_post)
    event = _event()

    assert paypal_ui._verify_paypal_webhook(event, _headers(cert_url)) is True
    assert posted["url"] == "https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature"
    assert posted["json"]["webhook_id"] == "WH-CONFIGURED"
    assert posted["json"]["webhook_event"] is event
    assert posted["json"]["cert_url"] == cert_url
    assert posted["timeout"] == 30


def test_signature_verification_logs_only_missing_headers_reason(monkeypatch, caplog):
    _sandbox(monkeypatch)
    monkeypatch.setattr(paypal_ui, "_paypal_token", lambda: pytest.fail("Unexpected PayPal request"))
    assert paypal_ui._verify_paypal_webhook(_event(), {}) is False
    assert caplog.messages == ["paypal_webhook_signature_rejected: missing_headers"]


@pytest.mark.parametrize("cert_url", [
    "http://api.sandbox.paypal.com/v1/notifications/certs/CERT-1",
    "https://user@api.sandbox.paypal.com/v1/notifications/certs/CERT-1",
    "https://api.sandbox.paypal.com.evil.invalid/v1/notifications/certs/CERT-1",
    "https://api.sandbox.paypal.com:444/v1/notifications/certs/CERT-1",
    "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-1?extra=1",
    "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-1#extra",
    "https://api.sandbox.paypal.com/v1/notifications/certs/../other",
    "https://api-m.sandbox.paypal.com/v1/notifications/certs/%2e%2e",
    "https://api-m.sandbox.paypal.com/v1/notifications/other",
    "https://api-m.sandbox.paypal.com/v1/notifications/certs/",
    "https://api-m.paypal.com/v1/notifications/certs/CERT-1",
    "https://[invalid/v1/notifications/certs/CERT-1",
])
def test_signature_verification_rejects_out_of_policy_cert_urls(monkeypatch, caplog, cert_url):
    _sandbox(monkeypatch)
    monkeypatch.setattr(paypal_ui, "_paypal_token", lambda: pytest.fail("Unexpected PayPal request"))
    assert paypal_ui._verify_paypal_webhook(_event(), _headers(cert_url)) is False
    assert caplog.messages == ["paypal_webhook_signature_rejected: cert_host_not_allowed"]


@pytest.mark.parametrize("cert_url, allowed", [
    ("https://api-m.paypal.com/v1/notifications/certs/CERT-1", True),
    ("https://api.paypal.com/v1/notifications/certs/CERT-1", False),
    ("https://api.sandbox.paypal.com/v1/notifications/certs/CERT-1", False),
    ("https://api-m.sandbox.paypal.com/v1/notifications/certs/CERT-1", False),
])
def test_live_does_not_admit_sandbox_or_unverified_alternate_host(cert_url, allowed):
    assert paypal_ui._cert_url_allowed(cert_url, "live") is allowed


def test_paypal_signature_failure_returns_400_without_ledger_or_handoff(monkeypatch, caplog):
    _sandbox(monkeypatch)
    rejected = MagicMock(status_code=200)
    rejected.json.return_value = {"verification_status": "FAILURE", "debug": "not-for-logs"}
    monkeypatch.setattr(paypal_ui, "_paypal_post", lambda *a, **k: rejected)
    monkeypatch.setattr(paypal_ui, "pg", lambda: pytest.fail("Unverified event reached the DB"))
    monkeypatch.setattr(
        paypal_ui, "handoff_after_payment", lambda *a: pytest.fail("Unverified event triggered Danea")
    )

    with pytest.raises(HTTPException) as rejected_webhook:
        _post_webhook(_event(), _headers())

    assert rejected_webhook.value.status_code == 400
    assert caplog.messages == ["paypal_webhook_signature_rejected: verification_failed"]


def test_sandbox_order_72_already_paid_does_not_credit_or_send_danea_again(monkeypatch):
    # Synthetic fixture of the state reached by #72; never touches the staging order.
    _sandbox(monkeypatch)
    monkeypatch.setenv("QRFACILE_INVOICE_TO", "billing@example.test")
    monkeypatch.setattr(paypal_ui, "_paypal_post", lambda *a, **k: _Response())
    monkeypatch.setattr(
        paypal_ui, "grant_annual_units", lambda *a, **k: pytest.fail("Paid order received more credits")
    )
    monkeypatch.setattr(
        invoice_handoff, "send_email_message", lambda *a: pytest.fail("Danea was sent twice")
    )
    sent_at = datetime(2026, 11, 27, 17, 48, tzinfo=timezone.utc)
    order = dict(
        _order(),
        id=72,
        status="paid",
        paypal_capture_id="CAP-1",
        pack="annual_start",
        invoice_handoff_sent_at=sent_at,
        invoice_handoff_attempts=1,
    )
    webhook_conn = MagicMock()
    webhook_conn.__enter__.return_value = webhook_conn
    webhook_cur = webhook_conn.cursor.return_value.__enter__.return_value
    webhook_cur.fetchone.side_effect = [{"id": 100}, order, None]
    monkeypatch.setattr(paypal_ui, "pg", lambda: webhook_conn)
    mail_conn = MagicMock()
    mail_conn.__enter__.return_value = mail_conn
    mail_cur = mail_conn.cursor.return_value.__enter__.return_value
    mail_cur.fetchone.return_value = order
    monkeypatch.setattr(invoice_handoff, "pg", lambda: mail_conn)
    handoff_results = []

    def record_handoff(order_id):
        handoff_results.append((order_id, invoice_handoff.handoff_after_payment(order_id)))

    monkeypatch.setattr(paypal_ui, "handoff_after_payment", record_handoff)
    first = _post_webhook(_event(), _headers())
    duplicate = _post_webhook(_event(), _headers())

    assert first.status_code == duplicate.status_code == 200
    assert json.loads(first.body) == {"ok": True, "status": "processed"}
    assert json.loads(duplicate.body) == {"ok": True, "status": "duplicate"}
    assert handoff_results == [(72, "already_sent")]
    statements = [(" ".join(call.args[0].split()), call.args[1]) for call in webhook_cur.execute.call_args_list]
    assert len(statements) == 5
    assert "verified_at" in statements[0][0] and "'verified'" in statements[0][0]
    assert statements[2][0].startswith("UPDATE paypal_webhook_events")
    assert statements[2][1] == ("processed", 72, "CAP-1", None, "WH-1")
    assert "paypal_webhook_processed" in statements[3][0] and "processed" in statements[3][1]
    assert not any("credit_ledger" in sql or sql.startswith("UPDATE orders") for sql, _ in statements)
    mail_cur.execute.assert_called_once_with("SELECT * FROM orders WHERE id=%s FOR UPDATE", (72,))
    assert (order["invoice_handoff_sent_at"], order["invoice_handoff_attempts"]) == (sent_at, 1)


def test_webhook_migration_is_transactional_idempotent_and_minimizes_payloads():
    text = (ROOT / "sql" / "2026_paypal_webhook_events.sql").read_text()
    source = (ROOT / "qrfacile_app" / "paypal_ui.py").read_text()

    assert text.startswith("BEGIN;") and text.rstrip().endswith("COMMIT;")
    assert "CREATE TABLE IF NOT EXISTS paypal_webhook_events" in text
    assert "event_id TEXT NOT NULL UNIQUE" in text
    assert "payload_sha256 CHAR(64) NOT NULL" in text
    assert "payload JSON" not in text
    assert "received_at TYPE TIMESTAMPTZ" in text
    assert "legacy_event_requires_review" in text
    assert "payment_environment IN ('live', 'sandbox', 'unknown')" in text
    assert "ON CONFLICT (event_id) DO NOTHING" in source
    assert source.count("_fulfill_completed_order(") == 3
    assert "PAYMENT.CAPTURE.COMPLETED" in source
    assert "PAYMENT.CAPTURE.REFUNDED" in source
    assert "CUSTOMER.DISPUTE.CREATED" in source


def test_admin_review_is_admin_only_post_and_audited():
    source = (ROOT / "qrfacile_app" / "admin_paypal_webhooks_ui.py").read_text()
    admin_home = (ROOT / "qrfacile_app" / "admin_home_ui.py").read_text()

    assert '@router.get("/admin/paypal-webhooks"' in source
    assert '@router.post("/admin/paypal-webhooks/{event_id}/review")' in source
    assert 'require_any_role(request, ("admin",))' in source
    assert "require_csrf_or_same_origin(request)" in source
    assert "paypal_webhook_reviewed" in source
    assert "reviewed_at IS NULL" in source
    assert "maxlength=\"1000\"" in source
    assert '"acknowledged"' not in source
    assert '_RESOLUTIONS = {"resolved_external", "false_positive"}' in source
    assert "La revisione non esegue rimborsi" in source
    assert '("/admin/paypal-webhooks", "Eventi PayPal")' in admin_home
