BEGIN;

ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_sent_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_attempts INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash CHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    send_attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    CONSTRAINT email_verification_token_hash_format CHECK (token_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS idx_email_verification_user_active
    ON email_verification_tokens (user_id, expires_at DESC)
    WHERE used_at IS NULL AND revoked_at IS NULL;

CREATE OR REPLACE FUNCTION sync_email_verified_state()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.email_verified THEN
        NEW.email_verified_at := COALESCE(NEW.email_verified_at, now());
    ELSE
        NEW.email_verified_at := NULL;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_users_sync_email_verified ON users;
CREATE TRIGGER trg_users_sync_email_verified
BEFORE INSERT OR UPDATE OF email_verified ON users
FOR EACH ROW EXECUTE FUNCTION sync_email_verified_state();

COMMIT;
