BEGIN;

-- Preserve every existing account. Only accounts created after this migration
-- are required to complete the verified-email gate.
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verification_required BOOLEAN;
UPDATE users SET email_verification_required=FALSE WHERE email_verification_required IS NULL;
ALTER TABLE users ALTER COLUMN email_verification_required SET NOT NULL;
ALTER TABLE users ALTER COLUMN email_verification_required SET DEFAULT TRUE;

COMMIT;
