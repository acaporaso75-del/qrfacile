from qrfacile_app.services.wine_compliance_advisor import build_compliance_advice


def test_compliance_advisor_page_uses_ui_shell_keyword_contract(monkeypatch):
    from starlette.requests import Request

    from qrfacile_app import wine_compliance_advisor_ui as advisor_ui

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/app/wine/7/compliance-advisor",
            "query_string": b"",
            "headers": [],
        }
    )
    monkeypatch.setattr(
        advisor_ui,
        "require_any_role",
        lambda *_args: {
            "id": 3,
            "email": "owner@example.test",
            "role": "winery",
            "credits": {"available": 2},
        },
    )
    monkeypatch.setattr(advisor_ui, "_load_payload", lambda *_args: {})
    monkeypatch.setattr(advisor_ui, "run_explainable_wine_compliance", lambda _payload: {})
    monkeypatch.setattr(
        advisor_ui,
        "build_compliance_advice",
        lambda _report: {
            "actions": [],
            "priority_counts": {},
            "completion_percent": 100,
        },
    )

    response = advisor_ui.compliance_advisor_page(request, 7)

    assert response.status_code == 200
    body = response.body.decode()
    assert "Compliance Advisor" in body
    assert "owner@example.test" in body


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
