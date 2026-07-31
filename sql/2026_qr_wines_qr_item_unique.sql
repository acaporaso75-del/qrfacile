BEGIN;

-- This is an intentionally one-off staging repair.  Refuse to run against any
-- other database, even if this file is invoked accidentally.
DO $migration$
BEGIN
    IF current_database() <> 'qrfacile_staging_db' THEN
        RAISE EXCEPTION
            'staging-only migration: expected qrfacile_staging_db, got %',
            current_database();
    END IF;
END
$migration$;

-- Prevent a concurrent wine creation from changing the duplicate set between
-- validation, cleanup, and constraint creation.
LOCK TABLE qr_wines IN ACCESS EXCLUSIVE MODE;

DO $migration$
DECLARE
    duplicate_ids BIGINT[];
    unexpected_duplicate_count INTEGER;
    empty_wine_relation_count INTEGER;
    kept_asset_count INTEGER;
BEGIN
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
        (SELECT count(*) FROM wine_labels WHERE wine_id = 7)
      INTO empty_wine_relation_count;

    IF empty_wine_relation_count <> 0 THEN
        RAISE EXCEPTION
            'wine_id=7 is not empty: found % related rows',
            empty_wine_relation_count;
    END IF;

    SELECT count(*)
      INTO kept_asset_count
      FROM wine_assets
     WHERE wine_id = 8;

    IF kept_asset_count <> 2 THEN
        RAISE EXCEPTION
            'unexpected asset count for wine_id=8: expected 2, got %',
            kept_asset_count;
    END IF;
END
$migration$;

DELETE FROM qr_wines
 WHERE id = 7
   AND qr_item_id = 22;

DO $migration$
DECLARE
    remaining_duplicate_count INTEGER;
    kept_asset_count INTEGER;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM qr_wines WHERE id = 8 AND qr_item_id = 22
    ) THEN
        RAISE EXCEPTION 'wine_id=8 was not preserved for qr_item_id=22';
    END IF;

    IF EXISTS (SELECT 1 FROM qr_wines WHERE id = 7) THEN
        RAISE EXCEPTION 'wine_id=7 was not deleted';
    END IF;

    SELECT count(*) INTO kept_asset_count
      FROM wine_assets
     WHERE wine_id = 8;

    IF kept_asset_count <> 2 THEN
        RAISE EXCEPTION
            'wine_id=8 assets changed during cleanup: expected 2, got %',
            kept_asset_count;
    END IF;

    SELECT count(*)
      INTO remaining_duplicate_count
      FROM (
          SELECT qr_item_id
            FROM qr_wines
           GROUP BY qr_item_id
          HAVING count(*) > 1
      ) AS duplicates;

    IF remaining_duplicate_count <> 0 THEN
        RAISE EXCEPTION
            'cannot add uniqueness: % duplicate qr_item_id groups remain',
            remaining_duplicate_count;
    END IF;
END
$migration$;

ALTER TABLE qr_wines
    ADD CONSTRAINT uq_qr_wines_qr_item_id UNIQUE (qr_item_id);

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
VALUES (
    NULL,
    'migration',
    'qr_wines_duplicate_repaired',
    'qr_items',
    22,
    NULL,
    'sql/2026_qr_wines_qr_item_unique.sql',
    jsonb_build_object(
        'deleted_wine_id', 7,
        'kept_wine_id', 8,
        'kept_asset_count', 2,
        'constraint', 'uq_qr_wines_qr_item_id',
        'environment', current_database()
    ),
    now()
);

COMMIT;
