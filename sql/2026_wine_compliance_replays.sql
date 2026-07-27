BEGIN;

CREATE TABLE IF NOT EXISTS wine_compliance_replays (
    id BIGSERIAL PRIMARY KEY,
    replay_id UUID NOT NULL UNIQUE,
    wine_id BIGINT NOT NULL REFERENCES qr_wines(id) ON DELETE CASCADE,
    winery_id BIGINT NOT NULL REFERENCES wineries(id) ON DELETE CASCADE,
    actor_user_id BIGINT NULL REFERENCES users(id) ON DELETE SET NULL,
    reason TEXT NOT NULL DEFAULT 'manual',
    replay_schema_version TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    catalog_version TEXT NOT NULL,
    knowledge_version TEXT NOT NULL,
    snapshot_json JSONB NOT NULL,
    content_hash CHAR(64) NOT NULL,
    hash_algorithm TEXT NOT NULL DEFAULT 'SHA-256',
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
    publishable BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT wine_compliance_replays_hash_format
        CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT wine_compliance_replays_hash_algorithm
        CHECK (hash_algorithm = 'SHA-256')
);

CREATE INDEX IF NOT EXISTS idx_wine_compliance_replays_wine_created
    ON wine_compliance_replays (wine_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wine_compliance_replays_winery_created
    ON wine_compliance_replays (winery_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_wine_compliance_replays_versions
    ON wine_compliance_replays (engine_version, catalog_version, knowledge_version);

CREATE INDEX IF NOT EXISTS idx_wine_compliance_replays_publishable
    ON wine_compliance_replays (publishable, created_at DESC);

COMMENT ON TABLE wine_compliance_replays IS
    'Snapshot immutabili delle verifiche wine compliance con evidenze, versioni e hash SHA-256.';
COMMENT ON COLUMN wine_compliance_replays.snapshot_json IS
    'Snapshot canonico completo; non deve essere aggiornato dopo la creazione.';
COMMENT ON COLUMN wine_compliance_replays.content_hash IS
    'SHA-256 del contenuto firmato logicamente, esclusi replay_id e metadati hash.';

CREATE OR REPLACE FUNCTION reject_wine_compliance_replay_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'wine_compliance_replays è append-only: UPDATE e DELETE non consentiti';
END;
$$;

DROP TRIGGER IF EXISTS trg_wine_compliance_replays_no_update
    ON wine_compliance_replays;
CREATE TRIGGER trg_wine_compliance_replays_no_update
BEFORE UPDATE ON wine_compliance_replays
FOR EACH ROW EXECUTE FUNCTION reject_wine_compliance_replay_mutation();

DROP TRIGGER IF EXISTS trg_wine_compliance_replays_no_delete
    ON wine_compliance_replays;
CREATE TRIGGER trg_wine_compliance_replays_no_delete
BEFORE DELETE ON wine_compliance_replays
FOR EACH ROW EXECUTE FUNCTION reject_wine_compliance_replay_mutation();

COMMIT;
