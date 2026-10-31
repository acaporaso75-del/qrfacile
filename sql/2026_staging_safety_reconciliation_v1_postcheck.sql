BEGIN READ ONLY;

DO $$
DECLARE
    lifecycle_columns integer;
BEGIN
    IF current_database() <> 'qrfacile_staging_db'
       AND current_setting('qrfacile.target_database', true) IS DISTINCT FROM current_database() THEN
        RAISE EXCEPTION 'Database non autorizzato per il post-check: %', current_database();
    END IF;

    IF to_regclass('public.email_verification_tokens') IS NULL THEN
        RAISE EXCEPTION 'email_verification_tokens assente';
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
    IF lifecycle_columns <> 14 THEN
        RAISE EXCEPTION 'Colonne lifecycle incomplete: %/14', lifecycle_columns;
    END IF;

    IF EXISTS (SELECT 1 FROM studio_invites WHERE token_hash IS NOT NULL) THEN
        RAISE EXCEPTION 'Sono comparsi token_hash legacy non autorizzati';
    END IF;
    IF EXISTS (
        SELECT 1 FROM studio_invites
        WHERE status='pending' AND expires_at < extract(epoch from now())::bigint
    ) THEN
        RAISE EXCEPTION 'Invito scaduto riattivato';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM qrfacile_schema_migrations
        WHERE migration_id='2026_staging_safety_reconciliation_v1' AND state='applied'
    ) THEN
        RAISE EXCEPTION 'Ledger migrazione non aggiornato';
    END IF;
END
$$;

SELECT status, count(*) AS records
FROM studio_invites
GROUP BY status
ORDER BY status;

SELECT count(*) AS legacy_total,
       count(*) FILTER (WHERE token IS NOT NULL) AS plaintext_tokens,
       count(*) FILTER (WHERE token_hash IS NOT NULL) AS reconstructed_hashes
FROM studio_invites;

ROLLBACK;
