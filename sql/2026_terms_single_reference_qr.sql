BEGIN;

-- Additive legal version: preserve all prior acceptances and document hashes.
INSERT INTO legal_documents (
    document_key, version, title, content_sha256, effective_at
) VALUES (
    'terms',
    '2026-10-29',
    'Termini di servizio QRFACILE',
    'e51b1dd566b22c99cdb52c83b6c1ec5ac08ea002396049fb4b42b9c759df44f0', -- pragma: allowlist secret (public HTML SHA-256)
    TIMESTAMPTZ '2026-10-29 00:00:00+01'
)
ON CONFLICT (document_key, version) DO UPDATE SET
    title = EXCLUDED.title,
    content_sha256 = EXCLUDED.content_sha256,
    effective_at = EXCLUDED.effective_at,
    retired_at = NULL;

COMMIT;
