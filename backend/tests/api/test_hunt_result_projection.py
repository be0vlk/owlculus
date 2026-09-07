"""Large retained Hunts keep the same reader-specific content on every surface."""

import hashlib
import json
import time
import tracemalloc

from app.core.dependencies import get_current_user
from app.database.models import Case, CaseUserLink, Hunt, HuntExecution, HuntStep
from app.main import app


def test_many_hunt_steps_share_authorization_without_preserving_revoked_access(
    client, session, test_case, test_admin, test_user
):
    related = Case(case_number="RELATED", title="Related")
    hidden = Case(case_number="PRIVATE", title="Private")
    session.add_all([related, hidden])
    session.flush()
    related_link = CaseUserLink(case_id=related.id, user_id=test_user.id)
    session.add_all(
        [related_link, CaseUserLink(case_id=test_case.id, user_id=test_user.id)]
    )
    hunt = Hunt(
        name="large-scan",
        display_name="Large scan",
        description="Scan",
        category="Other",
        definition_json={"steps": []},
    )
    session.add(hunt)
    session.flush()
    output = {
        "plugin": "CorrelationScan",
        "results": [
            {
                "case_id": test_case.id,
                "entity_id": source,
                "entity_type": "person",
                "match_type": "email",
                "normalized_value": f"{source}@example.com",
                "matches": [
                    {
                        "case_id": case.id,
                        "entity_id": target,
                        "entity_name": case.title,
                        "fields": [
                            {"field": "email", "value": f"{target}@example.com"}
                        ],
                    }
                    for target in range(120)
                    for case in (related, hidden)
                ],
            }
            for source in range(12)
        ],
        "errors": [],
        "result_count": 12,
    }
    definitions = [{"step_id": "scan", "plugin_name": "CorrelationScan"}]
    outputs = {"scan": output}
    for index in range(24):
        key = f"derived{index}"
        definitions.append(
            {
                "step_id": key,
                "plugin_name": "OtherPlugin",
                "parameter_mapping": {
                    "input": (
                        "scan.results" if index == 0 else f"derived{index - 1}.results"
                    )
                },
            }
        )
        outputs[key] = {
            "results": [{"copied": "Private derived result", "padding": "x" * 4096}],
            "result_count": 1,
        }
    execution = HuntExecution(
        hunt_id=hunt.id,
        case_id=test_case.id,
        created_by_id=test_admin.id,
        initial_parameters={},
        status="completed",
        definition_snapshot={"steps": definitions},
        context_data={"step_outputs": outputs},
    )
    session.add(execution)
    session.flush()
    session.add_all(
        [
            HuntStep(
                execution_id=execution.id,
                step_id=definition["step_id"],
                plugin_name=definition["plugin_name"],
                parameters={},
                status="completed",
                output=outputs[definition["step_id"]],
            )
            for definition in definitions
        ]
    )
    session.commit()
    url = f"/api/hunts/executions/{execution.id}"
    for reader, user in (
        ("broad", test_admin),
        ("narrow", test_user),
        ("revoked", test_user),
    ):
        if reader == "revoked":
            session.delete(related_link)
            session.commit()
        # Requests finish before the loop advances to the next reader.
        app.dependency_overrides[get_current_user] = lambda: user  # noqa: B023
        tracemalloc.start()
        start = time.perf_counter()
        detail = client.get(url + "?include_steps=true")
        exported = client.get(url + "/export?format=json")
        elapsed = time.perf_counter() - start
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert detail.status_code == exported.status_code == 200
        steps = detail.json()["steps"]
        results = steps[0]["output"]["results"]
        assert (
            sum(len(group["matches"]) for group in results)
            == {"broad": 2880, "narrow": 1440, "revoked": 0}[reader]
        )
        assert ("Private derived result" in detail.text) == (reader == "broad")
        assert ("Private derived result" in exported.text) == (reader == "broad")
        if reader != "broad":
            assert "Private" not in detail.text + exported.text
        if reader == "revoked":
            assert "Related" not in detail.text + exported.text
        content = {
            "steps": [step["output"] for step in steps],
            "context": detail.json()["context_data"],
        }
        exported_content = exported.json()["execution"]
        assert [step["output"] for step in exported_content["steps"]] == content[
            "steps"
        ]
        assert exported_content["context_data"] == content["context"]
        digest = hashlib.sha256(
            json.dumps(content, sort_keys=True).encode()
        ).hexdigest()
        print(
            f"HUNT_PROJECTION {reader}: {elapsed:.3f}s, {peak / 1024 / 1024:.2f} MiB, sha256={digest}"
        )


def test_interrupted_scan_pages_detail_and_export_keep_authorized_partial_output(
    client, session, test_case, test_admin, test_user
):
    from app.database.models import HuntStepResult

    related = Case(case_number="VISIBLE", title="Visible Case")
    hidden = Case(case_number="SECRET", title="SECRET")
    session.add_all([related, hidden])
    session.flush()
    session.add_all(
        [
            CaseUserLink(case_id=case.id, user_id=test_user.id)
            for case in (test_case, related)
        ]
    )
    hunt = Hunt(
        name="interrupted-scan",
        display_name="Interrupted scan",
        description="Scan",
        category="Other",
        definition_json={"steps": []},
    )
    session.add(hunt)
    session.flush()
    execution = HuntExecution(
        hunt_id=hunt.id,
        case_id=test_case.id,
        created_by_id=test_admin.id,
        initial_parameters={},
        status="failed",
        definition_snapshot={
            "steps": [{"step_id": "scan", "plugin_name": "CorrelationScan"}]
        },
    )
    session.add(execution)
    session.flush()
    step = HuntStep(
        execution_id=execution.id,
        step_id="scan",
        plugin_name="CorrelationScan",
        parameters={},
        status="failed",
        error_details="SECRET worker error",
    )
    session.add(step)
    session.flush()
    events = [
        {
            "type": "data",
            "data": {
                "case_id": test_case.id,
                "entity_id": 10,
                "match_type": "exact_profile",
                "group_id": "profile",
                "continuation": "merge",
                "source_fields": [
                    {
                        "field": "social_media.linkedin",
                        "value": "https://example.com/Ada",
                    }
                ],
                "matches": [
                    {
                        "case_id": case.id,
                        "case_title": case.title,
                        "entity_id": 20,
                        "fields": [
                            {
                                "field": "usernames[0]",
                                "value": "https://example.com/Ada",
                            }
                        ],
                    }
                ],
            },
        }
        for case in (hidden, related)
    ] + [{"type": "error", "data": {"message": "SECRET worker error"}}]
    session.add_all(
        [
            HuntStepResult(step_id=step.id, sequence=index, payload=event)
            for index, event in enumerate(events, 1)
        ]
    )
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: test_user
    url = f"/api/hunts/executions/{execution.id}"
    first = client.get(url + "/steps/scan/results?limit=1").json()
    assert first["items"] == [] and first["next_cursor"] == 1
    second = client.get(url + "/steps/scan/results?limit=1&cursor=1").json()
    assert second["items"] == [events[1]]
    detail = client.get(url + "?include_steps=true")
    assert detail.status_code == 200
    projected = detail.json()["steps"][0]
    assert projected["status"] == "failed"
    assert projected["output"]["partial"] is True
    assert projected["output"]["results"] == [events[1]["data"]]
    assert (
        projected["output"]["errors"][0]["message"]
        == "Correlation scan could not complete. Available results may be partial."
    )
    for suffix in (
        "?include_steps=true",
        "/steps/scan/results",
        "/export?format=json",
        "/export?format=pdf",
    ):
        response = client.get(url + suffix)
        assert response.status_code == 200
        assert b"SECRET" not in response.content
    session.delete(session.get(CaseUserLink, (related.id, test_user.id)))
    session.commit()
    assert (
        client.get(url + "?include_steps=true").json()["steps"][0]["output"]["results"]
        == []
    )
