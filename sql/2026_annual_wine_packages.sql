BEGIN;

ALTER TABLE orders ADD COLUMN IF NOT EXISTS commercial_snapshot JSONB;
ALTER TABLE credit_ledger ADD COLUMN IF NOT EXISTS expires_at BIGINT;
ALTER TABLE credit_ledger ADD COLUMN IF NOT EXISTS annual_used INTEGER NOT NULL DEFAULT 0;

-- Historical grants have NULL expiry and retain their original terms.
CREATE OR REPLACE VIEW available_credit_ledger AS
SELECT id, user_id, credit_type,
       CASE WHEN expires_at IS NOT NULL
                  AND expires_at <= extract(epoch FROM statement_timestamp())::bigint
            THEN annual_used ELSE delta END AS delta,
       reason, ref_table, ref_id, created_at
FROM credit_ledger;

CREATE OR REPLACE VIEW credit_balance AS
SELECT user_id, credit_type, COALESCE(SUM(delta),0) AS balance
FROM available_credit_ledger GROUP BY user_id, credit_type;

CREATE OR REPLACE FUNCTION allocate_annual_wine_units() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    available BIGINT;
    remaining INTEGER;
    take_units INTEGER;
    grant_row RECORD;
BEGIN
    -- Serialize all credit movements for one customer, including legacy routes.
    PERFORM pg_advisory_xact_lock(72825, hashtext(NEW.user_id::text));
    IF NEW.expires_at IS NOT NULL AND
       (NEW.delta <= 0 OR NEW.credit_type <> 'wine' OR NEW.annual_used <> 0
        OR NEW.expires_at <= NEW.created_at) THEN
        RAISE EXCEPTION 'Invalid annual grant';
    END IF;
    IF NEW.delta < 0 AND NEW.credit_type = 'wine' THEN
        SELECT COALESCE(SUM(delta),0) INTO available
        FROM available_credit_ledger
        WHERE user_id=NEW.user_id AND credit_type='wine';
        IF available < -NEW.delta THEN
            RAISE EXCEPTION 'Insufficient available wine units' USING ERRCODE='23514';
        END IF;
        remaining := -NEW.delta;
        FOR grant_row IN
            SELECT id, delta - annual_used AS remaining_units
            FROM credit_ledger
            WHERE user_id=NEW.user_id AND credit_type='wine'
              AND expires_at > extract(epoch FROM statement_timestamp())::bigint
              AND delta > annual_used
            ORDER BY expires_at, id FOR UPDATE
        LOOP
            take_units := LEAST(remaining, grant_row.remaining_units);
            UPDATE credit_ledger SET annual_used=annual_used+take_units WHERE id=grant_row.id;
            remaining := remaining-take_units;
            EXIT WHEN remaining=0;
        END LOOP;
        -- Any remainder consumes perpetual legacy/free credits, not annual grants.
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS allocate_annual_wine_units_trigger ON credit_ledger;
CREATE TRIGGER allocate_annual_wine_units_trigger BEFORE INSERT ON credit_ledger
FOR EACH ROW EXECUTE FUNCTION allocate_annual_wine_units();

CREATE UNIQUE INDEX IF NOT EXISTS uq_annual_wine_order_grant
ON credit_ledger (ref_id) WHERE ref_table='orders' AND reason='annual_purchase';

COMMIT;
