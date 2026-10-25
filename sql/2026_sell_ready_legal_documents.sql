BEGIN;

-- SHA-256 values identify the reviewed 2026-10-25 public legal copy.
INSERT INTO legal_documents (
    document_key, version, title, content_sha256, effective_at
) VALUES
    (
        'terms',
        '2026-10-25',
        'Termini di servizio QRFACILE',
        '4e3e30e0ceb17cf81e2ca184088dcbbd9537e77391f1c20c499633f115f57945',
        TIMESTAMPTZ '2026-10-25 00:00:00+02'
    ),
    (
        'privacy',
        '2026-10-25',
        'Informativa privacy QRFACILE',
        'ceaa60c1cd64671486ab158f84a32a6ea2aa648d671d4a1bc6ab03947e8a2307',
        TIMESTAMPTZ '2026-10-25 00:00:00+02'
    )
ON CONFLICT (document_key, version) DO UPDATE SET
    title = EXCLUDED.title,
    content_sha256 = EXCLUDED.content_sha256,
    effective_at = EXCLUDED.effective_at,
    retired_at = NULL;

COMMIT;
