BEGIN;

-- Existing accounts remain usable. Annual checkout fails closed until the
-- nullable fields below are completed from the authenticated settings page.
ALTER TABLE wineries ADD COLUMN IF NOT EXISTS billing_address TEXT;
ALTER TABLE wineries ADD COLUMN IF NOT EXISTS billing_cap TEXT;
ALTER TABLE wineries ADD COLUMN IF NOT EXISTS billing_country TEXT;

COMMIT;
