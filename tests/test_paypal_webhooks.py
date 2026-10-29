from decimal import Decimal
from pathlib import Path

import pytest

from qrfacile_app import paypal_ui


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


def test_signature_verification_posts_required_fields_to_paypal(monkeypatch):
    posted = {}
    monkeypatch.setattr(paypal_ui, "PAYPAL_WEBHOOK_ID", "WH-CONFIGURED")
    monkeypatch.setattr(paypal_ui, "_paypal_token", lambda: "not-logged-token")

    def fake_post(url, **kwargs):
        posted.update({"url": url, **kwargs})
        return _Response()

    monkeypatch.setattr(paypal_ui.requests, "post", fake_post)
    headers = {
        "paypal-transmission-id": "T-1",
        "paypal-transmission-time": "2026-10-29T12:00:00Z",
        "paypal-cert-url": f"{paypal_ui.PAYPAL_BASE}/v1/notifications/certs/CERT-1",
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-transmission-sig": "signature-value",
    }
    event = _event()

    assert paypal_ui._verify_paypal_webhook(event, headers) is True
    assert posted["url"].endswith("/v1/notifications/verify-webhook-signature")
    assert posted["json"]["webhook_id"] == "WH-CONFIGURED"
    assert posted["json"]["webhook_event"] is event
    assert posted["timeout"] == 30


def test_signature_verification_rejects_missing_headers_or_wrong_cert_host(monkeypatch):
    monkeypatch.setattr(paypal_ui, "PAYPAL_WEBHOOK_ID", "WH-CONFIGURED")
    assert paypal_ui._verify_paypal_webhook(_event(), {}) is False
    headers = {
        "paypal-transmission-id": "T-1",
        "paypal-transmission-time": "2026-10-29T12:00:00Z",
        "paypal-cert-url": "https://example.invalid/cert",
        "paypal-auth-algo": "SHA256withRSA",
        "paypal-transmission-sig": "signature-value",
    }
    assert paypal_ui._verify_paypal_webhook(_event(), headers) is False


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
