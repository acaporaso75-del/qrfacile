BEGIN;

SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '5min';

SELECT pg_advisory_xact_lock(hashtextextended('qrfacile:staging-safety-reconciliation-v1', 0));

DO $$
DECLARE
    lifecycle_columns integer;
    legacy_total bigint;
    legacy_tokens bigint;
    legacy_unused bigint;
    legacy_used bigint;
    legacy_expired bigint;
BEGIN
    IF current_database() <> 'qrfacile_staging_db'
       AND current_setting('qrfacile.target_database', true) IS DISTINCT FROM current_database() THEN
        RAISE EXCEPTION 'Database non autorizzato per la riconciliazione: %', current_database();
    END IF;

    IF to_regclass('public.users') IS NULL
       OR to_regclass('public.studio_invites') IS NULL
       OR to_regclass('public.invites') IS NULL THEN
        RAISE EXCEPTION 'Schema base incompleto: users, studio_invites e invites sono obbligatorie';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='users' AND column_name='email_verified'
    ) THEN
        RAISE EXCEPTION 'Colonna users.email_verified assente';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='pgcrypto') THEN
        RAISE EXCEPTION 'Estensione pgcrypto assente; installazione amministrativa separata richiesta';
    END IF;

    SELECT count(*) INTO lifecycle_columns
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='studio_invites'
      AND column_name IN (
        'token_hash','status','email_delivery_status','email_last_error',
        'email_last_attempt_at','email_sent_at','send_attempts','revoked_at',
        'revoked_by_user_id','accepted_at','acceptance_attempts',
        'last_acceptance_attempt_at','rate_limit_window_started_at','rate_limit_count'
      );

    IF lifecycle_columns NOT IN (0, 14) THEN
        RAISE EXCEPTION 'Schema studio_invites parziale e non riconciliabile automaticamente: %/14 colonne', lifecycle_columns;
    END IF;
    IF lifecycle_columns = 14 THEN
        IF to_regclass('public.qrfacile_schema_migrations') IS NULL THEN
            RAISE EXCEPTION 'Colonne lifecycle già presenti senza ledger riconosciuto';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM qrfacile_schema_migrations
            WHERE migration_id='2026_staging_safety_reconciliation_v1'
              AND state='applied'
        ) THEN
            RAISE EXCEPTION 'Colonne lifecycle presenti ma migrazione non registrata come applicata';
        END IF;
    END IF;

    SELECT count(*), count(*) FILTER (WHERE token IS NOT NULL),
           count(*) FILTER (WHERE used_at IS NULL),
           count(*) FILTER (WHERE used_at IS NOT NULL),
           count(*) FILTER (WHERE expires_at < extract(epoch from now())::bigint)
      INTO legacy_total, legacy_tokens, legacy_unused, legacy_used, legacy_expired
    FROM studio_invites;

    IF lifecycle_columns = 0 AND current_database() = 'qrfacile_staging_db'
       AND (legacy_total <> 17 OR legacy_tokens <> 0 OR legacy_unused <> 15
            OR legacy_used <> 2 OR legacy_expired < 16) THEN
        RAISE EXCEPTION
          'Inventario legacy cambiato: total %, token %, unused %, used %, expired %. Richiesto nuovo audit.',
          legacy_total, legacy_tokens, legacy_unused, legacy_used, legacy_expired;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS qrfacile_schema_migrations (
    migration_id text PRIMARY KEY,
    state text NOT NULL CHECK (state IN ('applying','applied','rolled_back')),
    applied_at timestamptz,
    rolled_back_at timestamptz,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

INSERT INTO qrfacile_schema_migrations (migration_id, state, metadata)
SELECT
    '2026_staging_safety_reconciliation_v1',
    'applying',
    jsonb_build_object(
        'database', current_database(),
        'email_table_existed', to_regclass('public.email_verification_tokens') IS NOT NULL,
        'user_email_verified_at_existed', EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='users' AND column_name='email_verified_at'
        ),
        'user_verification_sent_at_existed', EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='users' AND column_name='verification_sent_at'
        ),
        'user_verification_attempts_existed', EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='users' AND column_name='verification_attempts'
        ),
        'legacy_total', (SELECT count(*) FROM studio_invites),
        'legacy_tokens_present', (SELECT count(*) FROM studio_invites WHERE token IS NOT NULL)
    )
ON CONFLICT (migration_id) DO NOTHING;

ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at timestamptz;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_sent_at timestamptz;
ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_attempts integer NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash char(64) NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    used_at timestamptz,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at timestamptz,
    send_attempts integer NOT NULL DEFAULT 0,
    last_error text,
    CONSTRAINT ck_qrfacile_email_token_hash_format CHECK (token_hash ~ '^[0-9a-f]{64}$')
);

CREATE INDEX IF NOT EXISTS idx_qrfacile_email_verification_user_active
    ON email_verification_tokens (user_id, expires_at DESC)
    WHERE used_at IS NULL AND revoked_at IS NULL;

CREATE OR REPLACE FUNCTION qrfacile_sync_email_verified_state_v1()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.email_verified THEN
        NEW.email_verified_at := COALESCE(NEW.email_verified_at, now());
    ELSE
        NEW.email_verified_at := NULL;
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_qrfacile_sync_email_verified_v1 ON users;
CREATE TRIGGER trg_qrfacile_sync_email_verified_v1
BEFORE INSERT OR UPDATE OF email_verified ON users
FOR EACH ROW EXECUTE FUNCTION qrfacile_sync_email_verified_state_v1();

ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS token_hash char(64);
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'pending';
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS email_delivery_status text NOT NULL DEFAULT 'not_sent';
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS email_last_error text;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS email_last_attempt_at timestamptz;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS email_sent_at timestamptz;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS send_attempts integer NOT NULL DEFAULT 0;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS revoked_at timestamptz;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS revoked_by_user_id bigint;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS accepted_at timestamptz;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS acceptance_attempts integer NOT NULL DEFAULT 0;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS last_acceptance_attempt_at timestamptz;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS rate_limit_window_started_at timestamptz;
ALTER TABLE studio_invites ADD COLUMN IF NOT EXISTS rate_limit_count integer NOT NULL DEFAULT 0;

UPDATE studio_invites
SET status = CASE
        WHEN used_at IS NOT NULL THEN 'accepted'
        WHEN expires_at < extract(epoch from now())::bigint THEN 'expired'
        ELSE 'pending'
    END,
    accepted_at = CASE
        WHEN used_at IS NOT NULL THEN COALESCE(accepted_at, to_timestamp(used_at))
        ELSE accepted_at
    END
WHERE token_hash IS NULL;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM studio_invites WHERE token_hash IS NOT NULL) THEN
        RAISE EXCEPTION 'La riconciliazione non può ricostruire o accettare token legacy';
    END IF;
    IF EXISTS (
        SELECT 1 FROM studio_invites
        WHERE status='pending' AND expires_at < extract(epoch from now())::bigint
    ) THEN
        RAISE EXCEPTION 'Un invito scaduto risulta nuovamente pending';
    END IF;
END
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname='ck_qrfacile_studio_invites_status_v1'
          AND conrelid='public.studio_invites'::regclass
    ) THEN
        ALTER TABLE studio_invites ADD CONSTRAINT ck_qrfacile_studio_invites_status_v1
            CHECK (status IN ('pending','accepted','expired','revoked')) NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname='ck_qrfacile_studio_invites_delivery_v1'
          AND conrelid='public.studio_invites'::regclass
    ) THEN
        ALTER TABLE studio_invites ADD CONSTRAINT ck_qrfacile_studio_invites_delivery_v1
            CHECK (email_delivery_status IN ('not_sent','sending','sent','failed')) NOT VALID;
    END IF;
END
$$;

ALTER TABLE studio_invites VALIDATE CONSTRAINT ck_qrfacile_studio_invites_status_v1;
ALTER TABLE studio_invites VALIDATE CONSTRAINT ck_qrfacile_studio_invites_delivery_v1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_qrfacile_studio_invites_token_hash_v1
    ON studio_invites (token_hash) WHERE token_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_qrfacile_studio_invites_winery_status_v1
    ON studio_invites (winery_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_qrfacile_studio_invites_token_active_v1
    ON studio_invites (token_hash) WHERE used_at IS NULL AND revoked_at IS NULL;

CREATE OR REPLACE FUNCTION qrfacile_sync_studio_invite_lifecycle_v1()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.token IS NOT NULL AND NEW.token_hash IS NULL THEN
        NEW.token_hash := encode(digest(NEW.token, 'sha256'), 'hex');
    END IF;
    IF NEW.revoked_at IS NOT NULL THEN
        NEW.status := 'revoked';
    ELSIF NEW.used_at IS NOT NULL THEN
        NEW.status := 'accepted';
        NEW.accepted_at := COALESCE(NEW.accepted_at, now());
    ELSIF NEW.expires_at < extract(epoch from now())::bigint THEN
        NEW.status := 'expired';
    ELSE
        NEW.status := 'pending';
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_qrfacile_studio_invite_lifecycle_v1 ON studio_invites;
CREATE TRIGGER trg_qrfacile_studio_invite_lifecycle_v1
BEFORE INSERT OR UPDATE ON studio_invites
FOR EACH ROW EXECUTE FUNCTION qrfacile_sync_studio_invite_lifecycle_v1();

CREATE OR REPLACE FUNCTION qrfacile_limit_studio_invite_sends_v1()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.send_attempts > 10 THEN
        RAISE EXCEPTION 'Limite massimo di invii superato per questo invito';
    END IF;
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_qrfacile_limit_studio_invite_sends_v1 ON studio_invites;
CREATE TRIGGER trg_qrfacile_limit_studio_invite_sends_v1
BEFORE INSERT OR UPDATE OF send_attempts ON studio_invites
FOR EACH ROW EXECUTE FUNCTION qrfacile_limit_studio_invite_sends_v1();

UPDATE qrfacile_schema_migrations
SET state='applied', applied_at=now(), rolled_back_at=NULL
WHERE migration_id='2026_staging_safety_reconciliation_v1';

COMMIT;
