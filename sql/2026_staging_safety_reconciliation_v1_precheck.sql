BEGIN READ ONLY;

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

    IF lifecycle_columns = 0 AND current_database() = 'qrfacile_staging_db' THEN
        IF legacy_total <> 17 OR legacy_tokens <> 0 OR legacy_unused <> 15
           OR legacy_used <> 2 OR legacy_expired < 16 THEN
            RAISE EXCEPTION
              'Inventario legacy cambiato: total %, token %, unused %, used %, expired %. Richiesto nuovo audit.',
              legacy_total, legacy_tokens, legacy_unused, legacy_used, legacy_expired;
        END IF;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='pgcrypto') THEN
        RAISE EXCEPTION 'Estensione pgcrypto assente; installazione amministrativa separata richiesta';
    END IF;
END
$$;

SELECT current_database() AS database_name,
       current_user AS database_user,
       count(*) AS legacy_total,
       count(*) FILTER (WHERE token IS NOT NULL) AS legacy_tokens_present,
       count(*) FILTER (WHERE token IS NULL) AS legacy_tokens_null,
       count(*) FILTER (WHERE used_at IS NULL) AS legacy_unused,
       count(*) FILTER (WHERE used_at IS NOT NULL) AS legacy_used,
       count(*) FILTER (WHERE expires_at < extract(epoch from now())::bigint) AS legacy_expired
FROM studio_invites;

ROLLBACK;
