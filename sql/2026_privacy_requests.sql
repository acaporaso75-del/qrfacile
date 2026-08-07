BEGIN;

CREATE TABLE IF NOT EXISTS privacy_requests (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    request_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    details TEXT,
    resolution TEXT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    due_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    handled_by_user_id BIGINT,
    CHECK (request_type IN ('access','rectification','erasure','restriction','portability','objection')),
    CHECK (status IN ('open','identity_check','in_progress','completed','rejected'))
);

CREATE INDEX IF NOT EXISTS idx_privacy_requests_user
    ON privacy_requests (user_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_privacy_requests_status_due
    ON privacy_requests (status, due_at);

COMMIT;
