BEGIN;

-- Tracks the e-mail with invoice data and the Easyfatt-Xml file sent to the
-- internal billing office after a paid order. Existing orders stay NULL: no
-- hand-off is sent retroactively.
ALTER TABLE orders ADD COLUMN IF NOT EXISTS invoice_handoff_sent_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS invoice_handoff_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN IF NOT EXISTS invoice_handoff_last_error TEXT;

COMMIT;
