BEGIN;

CREATE TABLE IF NOT EXISTS paypal_webhook_events (
    id BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    payment_environment TEXT NOT NULL DEFAULT 'unknown',
    verification_status TEXT NOT NULL DEFAULT 'received',
    order_id BIGINT REFERENCES orders(id) ON DELETE SET NULL,
    resource_id TEXT,
    paypal_order_id TEXT,
    paypal_capture_id TEXT,
    payload_sha256 CHAR(64) NOT NULL,
    failure_code TEXT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    verified_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ
);

DO $migration$
DECLARE
    received_at_type TEXT;
BEGIN
    SELECT data_type
      INTO received_at_type
      FROM information_schema.columns
     WHERE table_schema = 'public'
       AND table_name = 'paypal_webhook_events'
       AND column_name = 'received_at';

    IF received_at_type = 'bigint' THEN
        ALTER TABLE paypal_webhook_events
            ALTER COLUMN received_at TYPE TIMESTAMPTZ
            USING to_timestamp(received_at);
    ELSIF received_at_type <> 'timestamp with time zone' THEN
        RAISE EXCEPTION
            'paypal_webhook_events.received_at has unsupported type %',
            received_at_type;
    END IF;
END
$migration$;

ALTER TABLE paypal_webhook_events
    ADD COLUMN IF NOT EXISTS payment_environment TEXT,
    ADD COLUMN IF NOT EXISTS verification_status TEXT,
    ADD COLUMN IF NOT EXISTS order_id BIGINT REFERENCES orders(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS resource_id TEXT,
    ADD COLUMN IF NOT EXISTS paypal_order_id TEXT,
    ADD COLUMN IF NOT EXISTS paypal_capture_id TEXT,
    ADD COLUMN IF NOT EXISTS payload_sha256 CHAR(64),
    ADD COLUMN IF NOT EXISTS failure_code TEXT,
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS reviewed_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS review_resolution TEXT,
    ADD COLUMN IF NOT EXISTS review_notes TEXT;

UPDATE paypal_webhook_events
   SET event_id = COALESCE(event_id, 'legacy-' || id::text),
       event_type = COALESCE(event_type, 'LEGACY.UNKNOWN'),
       payment_environment = COALESCE(payment_environment, 'unknown'),
       verification_status = COALESCE(verification_status, 'manual_review'),
       payload_sha256 = COALESCE(
           payload_sha256,
           md5('legacy-event:' || id::text) || md5('legacy-payload:' || id::text)
       ),
       failure_code = COALESCE(failure_code, 'legacy_event_requires_review')
 WHERE event_id IS NULL
    OR event_type IS NULL
    OR payment_environment IS NULL
    OR verification_status IS NULL
    OR payload_sha256 IS NULL;

ALTER TABLE paypal_webhook_events
    ALTER COLUMN event_id SET NOT NULL,
    ALTER COLUMN event_type SET NOT NULL,
    ALTER COLUMN payment_environment SET DEFAULT 'unknown',
    ALTER COLUMN payment_environment SET NOT NULL,
    ALTER COLUMN verification_status SET DEFAULT 'received',
    ALTER COLUMN verification_status SET NOT NULL,
    ALTER COLUMN payload_sha256 SET NOT NULL,
    ALTER COLUMN received_at SET DEFAULT now(),
    ALTER COLUMN received_at SET NOT NULL;

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'paypal_webhook_environment_check'
           AND conrelid = 'public.paypal_webhook_events'::regclass
    ) THEN
        ALTER TABLE paypal_webhook_events
            ADD CONSTRAINT paypal_webhook_environment_check
            CHECK (payment_environment IN ('live', 'sandbox', 'unknown'));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'paypal_webhook_status_check'
           AND conrelid = 'public.paypal_webhook_events'::regclass
    ) THEN
        ALTER TABLE paypal_webhook_events
            ADD CONSTRAINT paypal_webhook_status_check
            CHECK (verification_status IN (
                'received', 'verified', 'processed', 'ignored', 'manual_review', 'failed'
            ));
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'paypal_webhook_payload_hash_check'
           AND conrelid = 'public.paypal_webhook_events'::regclass
    ) THEN
        ALTER TABLE paypal_webhook_events
            ADD CONSTRAINT paypal_webhook_payload_hash_check
            CHECK (payload_sha256 ~ '^[0-9a-f]{64}$');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'paypal_webhook_review_resolution_check'
           AND conrelid = 'public.paypal_webhook_events'::regclass
    ) THEN
        ALTER TABLE paypal_webhook_events
            ADD CONSTRAINT paypal_webhook_review_resolution_check
            CHECK (
                review_resolution IS NULL
                OR review_resolution IN ('acknowledged', 'resolved_external', 'false_positive')
            );
    END IF;
END
$migration$;

CREATE INDEX IF NOT EXISTS idx_paypal_webhook_order
    ON paypal_webhook_events (order_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_paypal_webhook_review
    ON paypal_webhook_events (verification_status, received_at DESC)
    WHERE verification_status IN ('manual_review', 'failed');
CREATE INDEX IF NOT EXISTS idx_paypal_webhook_paypal_order
    ON paypal_webhook_events (paypal_order_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_paypal_webhook_unreviewed
    ON paypal_webhook_events (received_at DESC)
    WHERE verification_status IN ('manual_review', 'failed') AND reviewed_at IS NULL;

COMMIT;
