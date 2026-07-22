from pathlib import Path


def test_elabel_public_code_has_no_known_tracking_snippets():
    """Prevent accidental addition of common trackers to public e-label code."""
    root = Path(__file__).resolve().parents[1] / "qrfacile_app"
    candidates = [
        root / "public.py",
        root / "publish_routes.py",
        root / "wine_compliance_ui.py",
    ]
    forbidden = (
        "googletagmanager.com",
        "google-analytics.com",
        "connect.facebook.net",
        "facebook.com/tr",
        "hotjar.com",
        "clarity.ms",
    )

    scanned = 0
    for path in candidates:
        if not path.exists():
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for marker in forbidden:
            assert marker not in text, f"Tracking marker {marker} found in {path.name}"

    assert scanned > 0, "No public e-label modules were available for compliance scanning"


def test_ai_policy_requires_human_review():
    path = Path(__file__).resolve().parents[1] / "qrfacile_app" / "compliance_ui.py"
    text = path.read_text(encoding="utf-8")
    assert "human_review_required" in text
    assert "pending" in text
    assert "non devono essere pubblicati automaticamente" in text


def test_security_middleware_blocks_framing_and_sniffing():
    path = Path(__file__).resolve().parents[1] / "qrfacile_app" / "security_middleware.py"
    text = path.read_text(encoding="utf-8")
    assert 'X-Frame-Options", "DENY"' in text
    assert 'X-Content-Type-Options", "nosniff"' in text
    assert "frame-ancestors 'none'" in text
