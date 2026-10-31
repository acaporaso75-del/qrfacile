BEGIN;

ALTER TABLE studio_invites
    ALTER COLUMN token DROP NOT NULL;

ALTER TABLE studio_invites
    ADD COLUMN IF NOT EXISTS acceptance_attempts INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_acceptance_attempt_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rate_limit_window_started_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS rate_limit_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_studio_invites_token_hash_active
    ON studio_invites (token_hash)
    WHERE used_at IS NULL AND revoked_at IS NULL;

CREATE OR REPLACE FUNCTION qrfacile_limit_studio_invite_sends()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.send_attempts > 10 THEN
        RAISE EXCEPTION 'Limite massimo di invii superato per questo invito';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_limit_studio_invite_sends ON studio_invites;
CREATE TRIGGER trg_limit_studio_invite_sends
BEFORE INSERT OR UPDATE OF send_attempts ON studio_invites
FOR EACH ROW EXECUTE FUNCTION qrfacile_limit_studio_invite_sends();

COMMENT ON COLUMN studio_invites.token IS
    'Token transitorio in chiaro; viene azzerato all’accettazione. La lookup primaria usa token_hash.';
COMMENT ON COLUMN studio_invites.token_hash IS
    'SHA-256 del token di invito usato per identificazione e gestione sicura.';

COMMIT;
