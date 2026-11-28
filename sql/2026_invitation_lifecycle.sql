BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS token_hash CHAR(64);
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS email_delivery_status TEXT NOT NULL DEFAULT 'not_sent';
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS email_last_error TEXT;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS email_last_attempt_at TIMESTAMPTZ;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS email_sent_at TIMESTAMPTZ;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS send_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS revoked_by_user_id BIGINT;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS accepted_at TIMESTAMPTZ;

UPDATE studio_invites
SET token_hash = encode(digest(token, 'sha256'), 'hex')
WHERE token IS NOT NULL AND token_hash IS NULL;

UPDATE studio_invites
SET status = CASE
    WHEN revoked_at IS NOT NULL THEN 'revoked'
    WHEN used_at IS NOT NULL THEN 'accepted'
    WHEN expires_at IS NOT NULL AND expires_at < extract(epoch from now())::bigint THEN 'expired'
    ELSE 'pending'
END;

CREATE UNIQUE INDEX IF NOT EXISTS uq_studio_invites_token_hash
    ON studio_invites (token_hash)
    WHERE token_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_studio_invites_winery_status
    ON studio_invites (winery_id, status, created_at DESC);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname='studio_invites_status_check'
          AND conrelid='public.studio_invites'::regclass
    ) THEN
        ALTER TABLE studio_invites
            ADD CONSTRAINT studio_invites_status_check
            CHECK (status IN ('pending','accepted','expired','revoked'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname='studio_invites_delivery_check'
          AND conrelid='public.studio_invites'::regclass
    ) THEN
        ALTER TABLE studio_invites
            ADD CONSTRAINT studio_invites_delivery_check
            CHECK (email_delivery_status IN ('not_sent','sending','sent','failed'));
    END IF;
END $$;

CREATE OR REPLACE FUNCTION sync_studio_invite_lifecycle()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.token IS NOT NULL THEN
        NEW.token_hash := encode(digest(NEW.token, 'sha256'), 'hex');
    END IF;

    IF NEW.revoked_at IS NOT NULL THEN
        NEW.status := 'revoked';
    ELSIF NEW.used_at IS NOT NULL THEN
        NEW.status := 'accepted';
        NEW.accepted_at := COALESCE(NEW.accepted_at, now());
    ELSIF NEW.expires_at IS NOT NULL AND NEW.expires_at < extract(epoch from now())::bigint THEN
        NEW.status := 'expired';
    ELSE
        NEW.status := 'pending';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_studio_invites_lifecycle ON studio_invites;
CREATE TRIGGER trg_studio_invites_lifecycle
BEFORE INSERT OR UPDATE ON studio_invites
FOR EACH ROW EXECUTE FUNCTION sync_studio_invite_lifecycle();

COMMIT;
