from qrfacile_app.services.wine_compliance_advisor import build_compliance_advice


def _report(results, counts=None, publishable=False):
    return {
        "engine_version": "test-engine",
        "catalog_version": "test-catalog",
        "knowledge_version": "test-knowledge",
        "score": 60,
        "publishable": publishable,
        "counts": counts or {"PASS": 0, "WARNING": 0, "ERROR": len(results)},
        "results": results,
    }


def test_blocking_error_is_first_action():
    advice = build_compliance_advice(_report([
        {
            "rule_id": "WARN-1",
            "status": "WARNING",
            "title": "Warning",
            "explanation": "Da verificare",
            "remediation": "Controllare",
            "blocking": False,
            "human_review_required": True,
        },
        {
            "rule_id": "ERR-1",
            "status": "ERROR",
            "title": "Errore",
            "explanation": "Dato mancante",
            "remediation": "Compilare",
            "blocking": True,
            "human_review_required": True,
        },
    ], counts={"PASS": 0, "WARNING": 1, "ERROR": 1}))

    assert advice["next_action"]["rule_id"] == "ERR-1"
    assert advice["next_action"]["priority"] == "BLOCKING"
    assert advice["priority_counts"]["BLOCKING"] == 1
    assert advice["priority_counts"]["MEDIUM"] == 1


def test_passed_checks_do_not_create_actions():
    advice = build_compliance_advice(_report([
        {
            "rule_id": "PASS-1",
            "status": "PASS",
            "title": "Superato",
            "blocking": False,
        }
    ], counts={"PASS": 1, "WARNING": 0, "ERROR": 0}, publishable=True))

    assert advice["total_actions"] == 0
    assert advice["next_action"] is None
    assert advice["completion_percent"] == 100
    assert advice["publishable"] is True


def test_estimate_scales_with_multiple_affected_fields():
    advice = build_compliance_advice(_report([
        {
            "rule_id": "NUT-1",
            "status": "WARNING",
            "title": "Campi mancanti",
            "explanation": "Valori incompleti",
            "remediation": "Completare",
            "blocking": False,
            "human_review_required": True,
            "evidence": {"missing_fields": ["fat", "salt", "protein"]},
        }
    ], counts={"PASS": 2, "WARNING": 1, "ERROR": 0}, publishable=True))

    assert advice["actions"][0]["estimated_minutes"] == 20
    assert advice["estimated_total_minutes"] == 20
    assert advice["completion_percent"] == 67


def test_knowledge_links_are_preserved():
    advice = build_compliance_advice(_report([
        {
            "rule_id": "ING-1",
            "status": "ERROR",
            "title": "Ingredienti",
            "explanation": "Assenti",
            "remediation": "Inserire",
            "blocking": True,
            "human_review_required": True,
            "knowledge_ids": ["KB-EU-ING"],
        }
    ]))

    assert advice["actions"][0]["knowledge_ids"] == ["KB-EU-ING"]
    assert advice["advisor_version"]
