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
CREATE UNIQUE INDEX IF NOT EXISTS uq_legal_acceptances_user_document_version
    ON legal_acceptances (user_id, document_key, document_version);

-- QRFacile already has a production audit_log table. Do not redefine it.
-- The application writes to the existing columns:
-- user_id, role, action, entity_type, entity_id, ip, user_agent, meta, created_at.
DO $$
BEGIN
    IF to_regclass('public.audit_log') IS NULL THEN
        CREATE TABLE audit_log (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT,
            role TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id BIGINT,
            ip TEXT,
            user_agent TEXT,
            meta JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS ix_audit_action_time ON audit_log (action, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_entity ON audit_log (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_user_time ON audit_log (user_id, created_at DESC);

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
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS tenant_id BIGINT;
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS model_version TEXT;
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS prompt_template_version TEXT;
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS risk_classification TEXT NOT NULL DEFAULT 'limited';
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS contains_personal_data BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS human_review_required BOOLEAN NOT NULL DEFAULT true;
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS human_review_status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS reviewer_user_id BIGINT;
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS incident_reference TEXT;
ALTER TABLE ai_usage_log ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
CREATE INDEX IF NOT EXISTS idx_ai_usage_log_user ON ai_usage_log (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_usage_log_review ON ai_usage_log (human_review_status, created_at);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ai_usage_log_review_status_check'
          AND conrelid = 'public.ai_usage_log'::regclass
    ) THEN
        ALTER TABLE ai_usage_log
            ADD CONSTRAINT ai_usage_log_review_status_check
            CHECK (human_review_status IN ('pending', 'approved', 'rejected', 'not_required'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ai_usage_log_publish_review_check'
          AND conrelid = 'public.ai_usage_log'::regclass
    ) THEN
        ALTER TABLE ai_usage_log
            ADD CONSTRAINT ai_usage_log_publish_review_check
            CHECK (published_at IS NULL OR human_review_status IN ('approved', 'not_required'));
    END IF;
END $$;

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
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_compliance_incidents_status
    ON compliance_incidents (status, opened_at DESC);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'compliance_incidents_severity_check'
          AND conrelid = 'public.compliance_incidents'::regclass
    ) THEN
        ALTER TABLE compliance_incidents
            ADD CONSTRAINT compliance_incidents_severity_check
            CHECK (severity IN ('low', 'medium', 'high', 'critical'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'compliance_incidents_status_check'
          AND conrelid = 'public.compliance_incidents'::regclass
    ) THEN
        ALTER TABLE compliance_incidents
            ADD CONSTRAINT compliance_incidents_status_check
            CHECK (status IN ('open', 'investigating', 'contained', 'closed'));
    END IF;
END $$;

COMMIT;
