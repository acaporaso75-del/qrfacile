BEGIN;

-- SHA-256 values identify the reviewed 2026-10-25 public legal copy.
INSERT INTO legal_documents (
    document_key, version, title, content_sha256, effective_at
) VALUES
    (
        'terms',
        '2026-10-25',
        'Termini di servizio QRFACILE',
        '0fda722549411ad56d958685923f0ee66b12d59ceeb9305e0a4de2bc85f41d00', -- pragma: allowlist secret (public HTML SHA-256)
        TIMESTAMPTZ '2026-10-25 00:00:00+02'
    ),
    (
        'privacy',
        '2026-10-25',
        'Informativa privacy QRFACILE',
        'ceaa60c1cd64671486ab158f84a32a6ea2aa648d671d4a1bc6ab03947e8a2307', -- pragma: allowlist secret (public HTML SHA-256)
        TIMESTAMPTZ '2026-10-25 00:00:00+02'
    )
ON CONFLICT (document_key, version) DO UPDATE SET
    title = EXCLUDED.title,
    content_sha256 = EXCLUDED.content_sha256,
    effective_at = EXCLUDED.effective_at,
    retired_at = NULL;

COMMIT;
