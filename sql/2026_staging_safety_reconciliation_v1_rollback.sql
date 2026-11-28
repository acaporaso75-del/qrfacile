BEGIN;

SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '5min';

SELECT pg_advisory_xact_lock(hashtextextended('qrfacile:staging-safety-reconciliation-v1', 0));

DO $$
BEGIN
    IF current_database() <> 'qrfacile_staging_db'
       AND current_setting('qrfacile.target_database', true) IS DISTINCT FROM current_database() THEN
        RAISE EXCEPTION 'Database non autorizzato per il rollback: %', current_database();
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM qrfacile_schema_migrations
        WHERE migration_id='2026_staging_safety_reconciliation_v1' AND state='applied'
    ) THEN
        RAISE EXCEPTION 'Migrazione applicata non trovata nel ledger';
    END IF;
END
$$;

DROP TRIGGER IF EXISTS trg_qrfacile_limit_studio_invite_sends_v1 ON studio_invites;
DROP TRIGGER IF EXISTS trg_qrfacile_studio_invite_lifecycle_v1 ON studio_invites;
DROP FUNCTION IF EXISTS qrfacile_limit_studio_invite_sends_v1();
DROP FUNCTION IF EXISTS qrfacile_sync_studio_invite_lifecycle_v1();

DROP INDEX IF EXISTS idx_qrfacile_studio_invites_token_active_v1;
DROP INDEX IF EXISTS idx_qrfacile_studio_invites_winery_status_v1;
DROP INDEX IF EXISTS uq_qrfacile_studio_invites_token_hash_v1;
ALTER TABLE studio_invites DROP CONSTRAINT IF EXISTS ck_qrfacile_studio_invites_delivery_v1;
ALTER TABLE studio_invites DROP CONSTRAINT IF EXISTS ck_qrfacile_studio_invites_status_v1;

ALTER TABLE studio_invites
    DROP COLUMN IF EXISTS rate_limit_count,
    DROP COLUMN IF EXISTS rate_limit_window_started_at,
    DROP COLUMN IF EXISTS last_acceptance_attempt_at,
    DROP COLUMN IF EXISTS acceptance_attempts,
    DROP COLUMN IF EXISTS accepted_at,
    DROP COLUMN IF EXISTS revoked_by_user_id,
    DROP COLUMN IF EXISTS revoked_at,
    DROP COLUMN IF EXISTS send_attempts,
    DROP COLUMN IF EXISTS email_sent_at,
    DROP COLUMN IF EXISTS email_last_attempt_at,
    DROP COLUMN IF EXISTS email_last_error,
    DROP COLUMN IF EXISTS email_delivery_status,
    DROP COLUMN IF EXISTS status,
    DROP COLUMN IF EXISTS token_hash;

DROP TRIGGER IF EXISTS trg_qrfacile_sync_email_verified_v1 ON users;
DROP FUNCTION IF EXISTS qrfacile_sync_email_verified_state_v1();
DROP INDEX IF EXISTS idx_qrfacile_email_verification_user_active;

DO $$
DECLARE
    metadata jsonb;
BEGIN
    SELECT m.metadata INTO metadata
    FROM qrfacile_schema_migrations AS m
    WHERE migration_id='2026_staging_safety_reconciliation_v1';

    IF NOT COALESCE((metadata->>'email_table_existed')::boolean, false) THEN
        DROP TABLE IF EXISTS email_verification_tokens;
    END IF;
    IF NOT COALESCE((metadata->>'user_email_verified_at_existed')::boolean, false) THEN
        ALTER TABLE users DROP COLUMN IF EXISTS email_verified_at;
    END IF;
    IF NOT COALESCE((metadata->>'user_verification_sent_at_existed')::boolean, false) THEN
        ALTER TABLE users DROP COLUMN IF EXISTS verification_sent_at;
    END IF;
    IF NOT COALESCE((metadata->>'user_verification_attempts_existed')::boolean, false) THEN
        ALTER TABLE users DROP COLUMN IF EXISTS verification_attempts;
    END IF;
END
$$;

UPDATE qrfacile_schema_migrations
SET state='rolled_back', rolled_back_at=now()
WHERE migration_id='2026_staging_safety_reconciliation_v1';

COMMIT;
