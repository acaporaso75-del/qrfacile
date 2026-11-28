BEGIN;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS payment_environment TEXT NOT NULL DEFAULT 'unknown';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'orders_payment_environment_check'
          AND conrelid = 'public.orders'::regclass
    ) THEN
        ALTER TABLE orders
            ADD CONSTRAINT orders_payment_environment_check
            CHECK (payment_environment IN ('live', 'sandbox', 'manual', 'unknown'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_orders_paid_environment
    ON orders (payment_environment, paid_at DESC)
    WHERE status = 'paid';

-- Historical records are deliberately left as unknown: they must not be
-- represented as verified live revenue without provider evidence.
COMMIT;
