BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_legal_acceptance_user_document_version
    ON legal_acceptances (user_id, document_key, document_version)
    WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_legal_documents_active
    ON legal_documents (document_key, effective_at DESC)
    WHERE retired_at IS NULL;

COMMIT;
