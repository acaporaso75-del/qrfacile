BEGIN;

SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '5min';

SELECT pg_advisory_xact_lock(
    hashtextextended('qrfacile:production-qr-wines-unique-2026', 0)
);

DO $migration$
BEGIN
    IF current_database() <> 'qrfacile_db'
       AND current_setting('qrfacile.target_database', true) IS DISTINCT FROM current_database() THEN
        RAISE EXCEPTION
            'production migration: expected qrfacile_db, got %',
            current_database();
    END IF;
END
$migration$;

LOCK TABLE qr_wines IN ACCESS EXCLUSIVE MODE;

DO $migration$
DECLARE
    duplicate_ids BIGINT[];
    unexpected_duplicate_count INTEGER;
    discarded_relation_count INTEGER;
    kept_asset_count INTEGER;
    kept_label_count INTEGER;
    discarded_fingerprint TEXT;
    kept_fingerprint TEXT;
    uniqueness_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'uq_qr_wines_qr_item_id'
           AND conrelid = 'public.qr_wines'::regclass
           AND contype = 'u'
    ) INTO uniqueness_exists;

    IF uniqueness_exists THEN
        IF EXISTS (
            SELECT 1
              FROM qr_wines
             GROUP BY qr_item_id
            HAVING count(*) > 1
        ) THEN
            RAISE EXCEPTION 'unique constraint exists but duplicate qr_item_id groups remain';
        END IF;
        IF EXISTS (SELECT 1 FROM qr_wines WHERE id = 7) OR NOT EXISTS (
            SELECT 1 FROM qr_wines WHERE id = 8 AND qr_item_id = 22
        ) THEN
            RAISE EXCEPTION 'already-applied state does not preserve wine_id=8 exclusively';
        END IF;
        RETURN;
    END IF;

    SELECT array_agg(id ORDER BY id)
      INTO duplicate_ids
      FROM qr_wines
     WHERE qr_item_id = 22;

    IF duplicate_ids IS DISTINCT FROM ARRAY[7::BIGINT, 8::BIGINT] THEN
        RAISE EXCEPTION
            'unexpected wines for qr_item_id=22: expected {7,8}, got %',
            duplicate_ids;
    END IF;

    SELECT count(*)
      INTO unexpected_duplicate_count
      FROM (
          SELECT qr_item_id
            FROM qr_wines
           WHERE qr_item_id <> 22 OR qr_item_id IS NULL
           GROUP BY qr_item_id
          HAVING count(*) > 1
      ) AS duplicates;

    IF unexpected_duplicate_count <> 0 THEN
        RAISE EXCEPTION
            'unexpected duplicate qr_item_id groups outside qr_item_id=22: %',
            unexpected_duplicate_count;
    END IF;

    SELECT
        (SELECT count(*) FROM wine_nutrition WHERE wine_id = 7) +
        (SELECT count(*) FROM wine_ingredients WHERE wine_id = 7) +
        (SELECT count(*) FROM wine_allergens WHERE wine_id = 7) +
        (SELECT count(*) FROM wine_recycle_items WHERE wine_id = 7) +
        (SELECT count(*) FROM wine_assets WHERE wine_id = 7) +
        (SELECT count(*) FROM wine_meta WHERE wine_id = 7) +
        (SELECT count(*) FROM wine_labels WHERE wine_id = 7) +
        (SELECT count(*) FROM wine_compliance_replays WHERE wine_id = 7)
      INTO discarded_relation_count;

    IF discarded_relation_count <> 0 THEN
        RAISE EXCEPTION
            'wine_id=7 is not empty: found % related rows',
            discarded_relation_count;
    END IF;

    SELECT md5(
               coalesce(wine_name, '') || '|' ||
               coalesce(vintage, '') || '|' ||
               coalesce(lot, '')
           )
      INTO discarded_fingerprint
      FROM qr_wines
     WHERE id = 7
       AND qr_item_id = 22
       AND winery_id = 4
       AND wine_master_id = 5
       AND qr_duration_years = 25
       AND ingredients_json IS NULL
       AND nutrition_json IS NULL
       AND allergens_json IS NULL
       AND recycling_json IS NULL
       AND label_image_path IS NULL;

    SELECT md5(
               coalesce(wine_name, '') || '|' ||
               coalesce(vintage, '') || '|' ||
               coalesce(lot, '')
           )
      INTO kept_fingerprint
      FROM qr_wines
     WHERE id = 8
       AND qr_item_id = 22
       AND winery_id = 4
       AND wine_master_id = 5
       AND qr_duration_years = 25;

    IF discarded_fingerprint IS DISTINCT FROM 'ef8c02025aa14cba54dbdc733fe3040d'
       OR kept_fingerprint IS DISTINCT FROM discarded_fingerprint THEN
        RAISE EXCEPTION
            'duplicate identity validation failed: discarded %, kept %',
            discarded_fingerprint,
            kept_fingerprint;
    END IF;

    SELECT count(*) INTO kept_asset_count
      FROM wine_assets
     WHERE wine_id = 8;
    SELECT count(*) INTO kept_label_count
      FROM wine_labels
     WHERE wine_id = 8;

    IF kept_asset_count <> 2 OR kept_label_count <> 1 THEN
        RAISE EXCEPTION
            'unexpected preserved content for wine_id=8: assets %, labels %',
            kept_asset_count,
            kept_label_count;
    END IF;

    DELETE FROM qr_wines
     WHERE id = 7
       AND qr_item_id = 22;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'expected empty duplicate wine_id=7 was not deleted';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM qr_wines
         GROUP BY qr_item_id
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'duplicate qr_item_id groups remain after repair';
    END IF;

    ALTER TABLE qr_wines
        ADD CONSTRAINT uq_qr_wines_qr_item_id UNIQUE (qr_item_id);
END
$migration$;

DO $migration$
DECLARE
    kept_asset_count INTEGER;
    kept_label_count INTEGER;
BEGIN
    IF EXISTS (SELECT 1 FROM qr_wines WHERE id = 7) OR NOT EXISTS (
        SELECT 1 FROM qr_wines WHERE id = 8 AND qr_item_id = 22
    ) THEN
        RAISE EXCEPTION 'post-check did not preserve wine_id=8 exclusively';
    END IF;

    SELECT count(*) INTO kept_asset_count FROM wine_assets WHERE wine_id = 8;
    SELECT count(*) INTO kept_label_count FROM wine_labels WHERE wine_id = 8;

    IF kept_asset_count <> 2 OR kept_label_count <> 1 THEN
        RAISE EXCEPTION
            'preserved wine content changed: assets %, labels %',
            kept_asset_count,
            kept_label_count;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'uq_qr_wines_qr_item_id'
           AND conrelid = 'public.qr_wines'::regclass
           AND contype = 'u'
    ) THEN
        RAISE EXCEPTION 'uq_qr_wines_qr_item_id was not created';
    END IF;
END
$migration$;

INSERT INTO audit_log (
    user_id,
    role,
    action,
    entity_type,
    entity_id,
    ip,
    user_agent,
    meta,
    created_at
)
SELECT
    NULL,
    'migration',
    'qr_wines_production_duplicate_repaired',
    'qr_items',
    22,
    NULL,
    'sql/2026_production_qr_wines_qr_item_unique.sql',
    jsonb_build_object(
        'deleted_empty_wine_id', 7,
        'kept_wine_id', 8,
        'kept_asset_count', 2,
        'kept_label_count', 1,
        'constraint', 'uq_qr_wines_qr_item_id',
        'environment', current_database()
    ),
    now()
WHERE NOT EXISTS (
    SELECT 1
      FROM audit_log
     WHERE action = 'qr_wines_production_duplicate_repaired'
       AND entity_type = 'qr_items'
       AND entity_id = 22
);

COMMIT;
