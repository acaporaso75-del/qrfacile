BEGIN;

-- Base for vertical QR modules (QRFacile Link at /d/<slug>, later Menu at
-- /r/<slug>...). Additive and idempotent: existing wine QR codes (/e/) and
-- the QR Link beta keep working unchanged.

ALTER TABLE qr_items ADD COLUMN IF NOT EXISTS module TEXT;
ALTER TABLE qr_items ADD COLUMN IF NOT EXISTS stats_level TEXT NOT NULL DEFAULT 'none';
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'qr_items_stats_level_check' AND conrelid = 'public.qr_items'::regclass
    ) THEN
        ALTER TABLE qr_items ADD CONSTRAINT qr_items_stats_level_check
            CHECK (stats_level IN ('none', 'counts', 'detailed'));
    END IF;
END $$;
CREATE INDEX IF NOT EXISTS idx_qr_items_module_owner ON qr_items (module, owner_user_id) WHERE module IS NOT NULL;

-- Aggregated scan counters only: no IP, user-agent, cookie or visitor id.
-- hour = -1 and empty device/lang for the "counts" level.
CREATE TABLE IF NOT EXISTS qr_scan_daily (
    qr_item_id BIGINT NOT NULL REFERENCES qr_items(id) ON DELETE CASCADE,
    day DATE NOT NULL,
    hour SMALLINT NOT NULL DEFAULT -1,
    device TEXT NOT NULL DEFAULT '',
    lang TEXT NOT NULL DEFAULT '',
    scans INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (qr_item_id, day, hour, device, lang)
);

-- On/off switches managed from /admin/modules (no restart, no deploy).
CREATE TABLE IF NOT EXISTS module_switches (
    key TEXT PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    updated_by BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO module_switches (key) VALUES
    ('link'), ('link_sales_it'), ('link_sales_foreign'), ('link_oss_threshold_exceeded')
ON CONFLICT (key) DO NOTHING;

-- Per-user billing profile (business and studio accounts; wineries keep
-- using their wineries row).
CREATE TABLE IF NOT EXISTS billing_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    customer_type TEXT NOT NULL CHECK (customer_type IN ('company', 'private', 'association')),
    country CHAR(2) NOT NULL,
    name TEXT NOT NULL,
    vat_number TEXT,
    fiscal_code TEXT,
    address TEXT,
    postcode TEXT,
    city TEXT,
    province TEXT,
    sdi TEXT,
    pec TEXT,
    invoice_email TEXT,
    vies_valid BOOLEAN,
    vies_checked_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS abuse_reports (
    id BIGSERIAL PRIMARY KEY,
    qr_item_id BIGINT REFERENCES qr_items(id) ON DELETE SET NULL,
    reason TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    handled_at TIMESTAMPTZ,
    handled_by BIGINT
);
CREATE INDEX IF NOT EXISTS idx_abuse_reports_open ON abuse_reports (created_at DESC) WHERE handled_at IS NULL;

ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users ADD CONSTRAINT users_role_check
    CHECK (role IN ('admin', 'winery', 'studio', 'collaborator', 'business'));
-- Name of the business for 'business' accounts (no winery row for them).
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name TEXT;
-- Module used last ('wine', 'link', ...): where the user lands after login.
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_module TEXT;

-- QR Link beta rows become module 'link', content type 'link'. The top-level
-- "url" stays for the beta code path.
UPDATE qr_items
SET module = 'link',
    payload = COALESCE(payload, '{}'::jsonb)
        || jsonb_build_object(
            'type', 'link',
            'content', jsonb_build_object('link', jsonb_build_object('url', payload->>'url'))
        )
WHERE qr_type = 'external'
  AND (module IS NULL OR payload->>'type' IS NULL);

COMMIT;
