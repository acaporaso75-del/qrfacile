from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "2026_production_qr_wines_qr_item_unique.sql"


def test_production_duplicate_repair_is_transactional_and_fail_closed():
    text = MIGRATION.read_text(encoding="utf-8")

    assert text.startswith("BEGIN;")
    assert text.rstrip().endswith("COMMIT;")
    assert "current_database() <> 'qrfacile_db'" in text
    assert "current_setting('qrfacile.target_database', true)" in text
    assert "LOCK TABLE qr_wines IN ACCESS EXCLUSIVE MODE" in text
    assert "ARRAY[7::BIGINT, 8::BIGINT]" in text
    assert "unexpected duplicate qr_item_id groups outside qr_item_id=22" in text
    assert "ef8c02025aa14cba54dbdc733fe3040d" in text


def test_production_repair_deletes_only_the_empty_duplicate():
    text = MIGRATION.read_text(encoding="utf-8")

    for relation in (
        "wine_nutrition",
        "wine_ingredients",
        "wine_allergens",
        "wine_recycle_items",
        "wine_assets",
        "wine_meta",
        "wine_labels",
        "wine_compliance_replays",
    ):
        assert f"FROM {relation} WHERE wine_id = 7" in text

    assert "DELETE FROM qr_wines\n     WHERE id = 7\n       AND qr_item_id = 22" in text
    assert "DELETE FROM qr_items" not in text
    assert "DELETE FROM wine_assets" not in text
    assert "DELETE FROM wine_labels" not in text
    assert "kept_asset_count <> 2 OR kept_label_count <> 1" in text


def test_production_repair_is_idempotent_and_audited_once():
    text = MIGRATION.read_text(encoding="utf-8")

    assert "IF uniqueness_exists THEN" in text
    assert "ADD CONSTRAINT uq_qr_wines_qr_item_id UNIQUE (qr_item_id)" in text
    assert "qr_wines_production_duplicate_repaired" in text
    assert "WHERE NOT EXISTS" in text
    assert "'deleted_empty_wine_id', 7" in text
    assert "'kept_wine_id', 8" in text
