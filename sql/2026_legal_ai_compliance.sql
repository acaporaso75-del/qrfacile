BEGIN;

CREATE TABLE IF NOT EXISTS legal_documents (
    id BIGSERIAL PRIMARY KEY,
    document_key TEXT NOT NULL,
    version TEXT NOT NULL,
    title TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    effective_at TIMESTAMPTZ NOT NULL,
    retired_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_key, version)
);

CREATE TABLE IF NOT EXISTS legal_acceptances (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT,
    document_key TEXT NOT NULL,
    document_version TEXT NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ip_address INET,
    user_agent TEXT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_legal_acceptances_user
    ON legal_acceptances (user_id, accepted_at DESC);

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_user_id BIGINT,
    actor_role TEXT,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    outcome TEXT NOT NULL DEFAULT 'success',
    request_id TEXT,
    ip_address INET,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_audit_log_occurred_at ON audit_log (occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log (resource_type, resource_id);

CREATE TABLE IF NOT EXISTS ai_usage_log (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id BIGINT,
    tenant_id BIGINT,
    use_case TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    model_version TEXT,
    input_sha256 TEXT NOT NULL,
    output_sha256 TEXT NOT NULL,
    prompt_template_version TEXT,
    risk_classification TEXT NOT NULL DEFAULT 'limited',
    contains_personal_data BOOLEAN NOT NULL DEFAULT false,
    human_review_required BOOLEAN NOT NULL DEFAULT true,
    human_review_status TEXT NOT NULL DEFAULT 'pending',
    reviewer_user_id BIGINT,
    reviewed_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    incident_reference TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (human_review_status IN ('pending', 'approved', 'rejected', 'not_required')),
    CHECK (published_at IS NULL OR human_review_status IN ('approved', 'not_required'))
);
CREATE INDEX IF NOT EXISTS idx_ai_usage_log_user ON ai_usage_log (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_usage_log_review ON ai_usage_log (human_review_status, created_at);

CREATE TABLE IF NOT EXISTS compliance_incidents (
    id BIGSERIAL PRIMARY KEY,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ,
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    summary TEXT NOT NULL,
    personal_data_involved BOOLEAN NOT NULL DEFAULT false,
    authority_notification_required BOOLEAN,
    authority_notified_at TIMESTAMPTZ,
    data_subject_notification_required BOOLEAN,
    data_subjects_notified_at TIMESTAMPTZ,
    owner_user_id BIGINT,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    CHECK (status IN ('open', 'investigating', 'contained', 'closed'))
);

COMMIT;
