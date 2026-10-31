from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "2026_qr_wines_qr_item_unique.sql"


def test_duplicate_cleanup_is_transactional_staging_only_and_fail_closed():
    text = MIGRATION.read_text(encoding="utf-8")

    assert text.startswith("BEGIN;")
    assert text.rstrip().endswith("COMMIT;")
    assert "current_database() <> 'qrfacile_staging_db'" in text
    assert "LOCK TABLE qr_wines IN ACCESS EXCLUSIVE MODE" in text
    assert "ARRAY[7::BIGINT, 8::BIGINT]" in text
    assert "unexpected duplicate qr_item_id groups outside qr_item_id=22" in text


def test_cleanup_deletes_only_empty_wine_7_and_preserves_wine_8_assets():
    text = MIGRATION.read_text(encoding="utf-8")

    for relation in (
        "wine_nutrition",
        "wine_ingredients",
        "wine_allergens",
        "wine_recycle_items",
        "wine_assets",
        "wine_meta",
        "wine_labels",
    ):
        assert f"FROM {relation} WHERE wine_id = 7" in text

    assert "DELETE FROM qr_wines\n WHERE id = 7\n   AND qr_item_id = 22" in text
    assert text.count("FROM wine_assets\n     WHERE wine_id = 8") == 2
    assert "wine_id=8 was not preserved" in text


def test_migration_adds_uniqueness_and_writes_duplicate_audit_event():
    text = MIGRATION.read_text(encoding="utf-8")

    assert "ADD CONSTRAINT uq_qr_wines_qr_item_id UNIQUE (qr_item_id)" in text
    assert "qr_wines_duplicate_repaired" in text
    assert "'deleted_wine_id', 7" in text
    assert "'kept_wine_id', 8" in text


def test_wine_creation_handles_only_the_expected_unique_violation():
    text = (ROOT / "qrfacile_app" / "premium_ui.py").read_text(encoding="utf-8")

    assert "from psycopg.errors import UniqueViolation" in text
    assert 'QR_WINES_QR_ITEM_UNIQUE_CONSTRAINT = "uq_qr_wines_qr_item_id"' in text
    assert "except UniqueViolation as exc:" in text
    assert "exc.diag.constraint_name == QR_WINES_QR_ITEM_UNIQUE_CONSTRAINT" in text
    assert "conn.rollback()" in text
    assert "Esiste%20gi%C3%A0%20un%20vino%20per%20questo%20QR" in text
