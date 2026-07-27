BEGIN;

CREATE TABLE IF NOT EXISTS ai_system_registry (
    id BIGSERIAL PRIMARY KEY,
    system_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    model_version TEXT,
    intended_purpose TEXT NOT NULL,
    prohibited_uses TEXT NOT NULL DEFAULT '',
    affected_users TEXT NOT NULL DEFAULT '',
    input_data_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
    output_categories JSONB NOT NULL DEFAULT '[]'::jsonb,
    contains_personal_data BOOLEAN NOT NULL DEFAULT false,
    special_category_data_allowed BOOLEAN NOT NULL DEFAULT false,
    risk_classification TEXT NOT NULL DEFAULT 'limited',
    transparency_notice_required BOOLEAN NOT NULL DEFAULT true,
    human_oversight_required BOOLEAN NOT NULL DEFAULT true,
    human_oversight_procedure TEXT NOT NULL,
    auto_publish_allowed BOOLEAN NOT NULL DEFAULT false,
    training_data_reuse_allowed BOOLEAN NOT NULL DEFAULT false,
    retention_days INTEGER,
    dpa_verified BOOLEAN NOT NULL DEFAULT false,
    transfer_mechanism TEXT,
    security_reviewed_at TIMESTAMPTZ,
    legal_reviewed_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    approved_by_user_id BIGINT,
    status TEXT NOT NULL DEFAULT 'draft',
    owner_user_id BIGINT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_system_registry_status
    ON ai_system_registry (status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_system_registry_provider
    ON ai_system_registry (provider, model);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ai_system_registry_status_check'
          AND conrelid = 'public.ai_system_registry'::regclass
    ) THEN
        ALTER TABLE ai_system_registry
            ADD CONSTRAINT ai_system_registry_status_check
            CHECK (status IN ('draft', 'assessment', 'approved', 'suspended', 'retired'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ai_system_registry_risk_check'
          AND conrelid = 'public.ai_system_registry'::regclass
    ) THEN
        ALTER TABLE ai_system_registry
            ADD CONSTRAINT ai_system_registry_risk_check
            CHECK (risk_classification IN ('minimal', 'limited', 'high', 'prohibited'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ai_system_registry_publish_check'
          AND conrelid = 'public.ai_system_registry'::regclass
    ) THEN
        ALTER TABLE ai_system_registry
            ADD CONSTRAINT ai_system_registry_publish_check
            CHECK (
                auto_publish_allowed = false
                OR (
                    status = 'approved'
                    AND human_oversight_required = false
                    AND risk_classification IN ('minimal', 'limited')
                )
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ai_system_registry_sensitive_data_check'
          AND conrelid = 'public.ai_system_registry'::regclass
    ) THEN
        ALTER TABLE ai_system_registry
            ADD CONSTRAINT ai_system_registry_sensitive_data_check
            CHECK (special_category_data_allowed = false OR contains_personal_data = true);
    END IF;
END $$;

COMMIT;
