from copy import deepcopy
from datetime import datetime, timezone

from qrfacile_app.services.wine_compliance_replay import (
    build_replay_snapshot,
    canonical_json,
    compare_replays,
    sha256_payload,
    verify_replay_snapshot,
)


def _payload(name: str = "Falanghina", kcal: str = "80") -> dict:
    return {
        "wine": {
            "wine_id": 10,
            "winery_id": 2,
            "wine_name": name,
            "vintage": "2025",
            "lot": "L01",
        },
        "nutrition": {
            "energy_kj": "335",
            "energy_kcal": kcal,
            "fat": "0",
            "saturates": "0",
            "carbs": "1.2",
            "sugars": "0.4",
            "protein": "0",
            "salt": "0",
        },
        "ingredients": ["Uva", "Conservante: solfiti"],
        "allergens": ["Solfiti"],
        "recycle": {"bottiglia": {"code": "GL 70"}},
        "meta": {"extra_ingredients": ""},
    }


def test_canonical_json_is_stable_across_key_order():
    left = {"b": 2, "a": {"d": 4, "c": 3}}
    right = {"a": {"c": 3, "d": 4}, "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert sha256_payload(left) == sha256_payload(right)


def test_replay_snapshot_contains_versions_evidence_advisor_and_valid_hash():
    snapshot = build_replay_snapshot(
        _payload(),
        actor_user_id=99,
        reason="publication",
        created_at=datetime(2026, 7, 27, 20, 0, tzinfo=timezone.utc),
    )
    assert snapshot["replay_schema_version"] == "2026.07.2"
    assert snapshot["actor_user_id"] == 99
    assert snapshot["reason"] == "publication"
    assert snapshot["engine_version"]
    assert snapshot["catalog_version"]
    assert snapshot["knowledge_version"]
    assert snapshot["advisor_version"]
    assert snapshot["report"]["results"]
    assert "actions" in snapshot["advisor"]
    assert all("evidence" in item for item in snapshot["report"]["results"])
    assert len(snapshot["content_hash"]) == 64
    assert verify_replay_snapshot(snapshot) is True


def test_tampered_replay_is_rejected_by_integrity_check():
    snapshot = build_replay_snapshot(_payload())
    tampered = deepcopy(snapshot)
    tampered["payload"]["wine"]["wine_name"] = "Nome alterato"
    assert verify_replay_snapshot(tampered) is False


def test_compare_replays_reports_data_score_and_advisor_changes():
    left = build_replay_snapshot(
        _payload(),
        created_at=datetime(2026, 7, 27, 20, 0, tzinfo=timezone.utc),
    )
    right = build_replay_snapshot(
        _payload(name="Falanghina Riserva", kcal="200"),
        created_at=datetime(2026, 7, 27, 21, 0, tzinfo=timezone.utc),
    )
    diff = compare_replays(left, right)
    changed_paths = {item["path"] for item in diff["changes"]}
    assert "payload.wine.wine_name" in changed_paths
    assert "payload.nutrition.energy_kcal" in changed_paths
    assert diff["change_count"] >= 2
    assert diff["left_replay_id"] == left["replay_id"]
    assert diff["right_replay_id"] == right["replay_id"]
    assert "completion_delta" in diff
    assert "action_count_delta" in diff


def test_compare_ignores_replay_identity_metadata():
    left = build_replay_snapshot(
        _payload(),
        created_at=datetime(2026, 7, 27, 20, 0, tzinfo=timezone.utc),
    )
    right = build_replay_snapshot(
        _payload(),
        created_at=datetime(2026, 7, 27, 21, 0, tzinfo=timezone.utc),
    )
    diff = compare_replays(left, right)
    assert diff["change_count"] == 0
