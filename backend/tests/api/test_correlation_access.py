"""Current-reader authorization of persisted correlation output."""

from copy import deepcopy

from app.core.dependencies import get_current_user
from app.database.models import (
    Case,
    CaseUserLink,
    ExecutionControl,
    ExecutionOutbox,
    PluginExecution,
    PluginExecutionResult,
)
from app.main import app


def group(source, related, label):
    return {
        "type": "data",
        "data": {
            "case_id": source.id,
            "entity_id": 10,
            "entity_name": label,
            "entity_type": "person",
            "match_type": "name",
            "matches": [
                {
                    "case_id": related.id,
                    "case_title": label,
                    "case_number": label,
                    "entity_id": 20,
                    "entity_name": label,
                    "found_in": label,
                }
            ],
        },
    }


def retain(session, source, user, events):
    execution = PluginExecution(
        case_id=source.id,
        created_by_id=user.id,
        plugin_name="CorrelationScan",
        parameters={},
        status="completed",
    )
    session.add(execution)
    session.flush()
    control = ExecutionControl(plugin_execution_id=execution.id)
    session.add(control)
    session.flush()
    session.add(ExecutionOutbox(control_id=control.id))
    for sequence, event in enumerate(events, 1):
        session.add(
            PluginExecutionResult(
                execution_id=execution.id, sequence=sequence, payload=event
            )
        )
    session.commit()
    return f"/api/plugins/executions/{execution.id}"


def test_retained_scan_filters_mixed_groups_and_advances_hidden_pages(
    client,
    session,
    test_case,
    test_admin,
    test_analyst,
):
    hidden = Case(case_number="SECRET", title="SECRET", created_by_id=test_admin.id)
    visible = Case(case_number="VISIBLE", title="VISIBLE", created_by_id=test_admin.id)
    session.add_all([hidden, visible])
    session.flush()
    source_link = CaseUserLink(case_id=test_case.id, user_id=test_analyst.id)
    related_link = CaseUserLink(case_id=visible.id, user_id=test_analyst.id)
    session.add_all([source_link, related_link])
    mixed = group(test_case, visible, "Visible source")
    mixed["data"]["matches"] += group(test_case, hidden, "SECRET")["data"]["matches"]
    originals = [
        group(test_case, hidden, "SECRET"),
        mixed,
        {"type": "complete", "data": {"message": "SECRET summary"}},
    ]
    url = retain(session, test_case, test_admin, originals)
    app.dependency_overrides[get_current_user] = lambda: test_analyst
    first = client.get(url + "/results?limit=1").json()
    assert first["items"] == []
    assert first["cursor"] == first["next_cursor"] == 1
    second = client.get(url + "/results?limit=1&cursor=1").json()
    assert len(second["items"]) == 1
    assert len(second["items"][0]["data"]["matches"]) == 1
    assert "SECRET" not in str(client.get(url + "/results").json())
    app.dependency_overrides[get_current_user] = lambda: test_admin
    assert len(client.get(url + "/results").json()["items"][1]["data"]["matches"]) == 2
    app.dependency_overrides[get_current_user] = lambda: test_analyst
    session.delete(related_link)
    session.commit()
    assert not any(
        e["type"] == "data" for e in client.get(url + "/results").json()["items"]
    )
    session.delete(source_link)
    session.commit()
    assert client.get(url + "/results").status_code == 403
    assert client.get(url).status_code == 403


def test_hunt_detail_chunks_context_and_exports_filter_the_same_scan(
    client,
    session,
    test_case,
    test_admin,
    test_analyst,
):
    from app.database.models import Hunt, HuntExecution, HuntStep, HuntStepResult

    hidden = Case(case_number="SECRET", title="SECRET")
    session.add(hidden)
    session.flush()
    session.add(CaseUserLink(case_id=test_case.id, user_id=test_analyst.id))
    hunt = Hunt(
        name="correlations",
        display_name="Correlations",
        description="Scan",
        category="Other",
        definition_json={"steps": []},
    )
    session.add(hunt)
    session.flush()
    payload = group(test_case, hidden, "SECRET")["data"]
    output = {
        "results": [payload],
        "result_count": 1,
        "plugin": "CorrelationScan",
        "errors": [{"message": "SECRET"}],
    }
    execution = HuntExecution(
        hunt_id=hunt.id,
        case_id=test_case.id,
        created_by_id=test_admin.id,
        initial_parameters={},
        status="completed",
        context_data={
            "step_outputs": {"scan": deepcopy(output)},
            "metadata": {"summary": "SECRET"},
        },
        error={"message": "SECRET"},
    )
    session.add(execution)
    session.flush()
    step = HuntStep(
        execution_id=execution.id,
        step_id="scan",
        plugin_name="CorrelationScan",
        parameters={},
        status="completed",
        output=output,
        error_details="SECRET",
    )
    session.add(step)
    session.flush()
    session.add(
        HuntStepResult(
            step_id=step.id, sequence=1, payload={"type": "data", "data": payload}
        )
    )
    session.commit()
    derived = HuntStep(
        execution_id=execution.id,
        step_id="followup",
        plugin_name="OtherPlugin",
        parameters={"query": "SECRET"},
        output={"results": [{"copied": "SECRET"}], "result_count": 1},
        error_details="SECRET",
    )
    session.add(derived)
    session.flush()
    session.add(
        HuntStepResult(
            step_id=derived.id,
            sequence=1,
            payload={"type": "data", "data": {"copied": "SECRET"}},
        )
    )
    execution.context_data = {
        **execution.context_data,
        "step_outputs": {
            **execution.context_data["step_outputs"],
            "followup": derived.output,
        },
    }
    session.commit()
    url = f"/api/hunts/executions/{execution.id}"
    app.dependency_overrides[get_current_user] = lambda: test_analyst
    for suffix in (
        "",
        "?include_steps=true",
        "/steps/scan/results",
        "/steps/followup/results",
        "/export?format=json",
    ):
        response = client.get(url + suffix)
        assert response.status_code == 200, response.text
        assert "SECRET" not in response.text
    app.dependency_overrides[get_current_user] = lambda: test_admin
    assert "SECRET" in client.get(url + "?include_steps=true").text
    assert "SECRET" in client.get(url + "/export?format=json").text


async def save_scan(session, source, related, initiator):
    from dataclasses import replace

    from app.database.models import Entity
    from app.plugins.correlation_plugin import CorrelationScan
    from app.plugins.plugin_context import PluginRun, ServiceEvidenceSink
    from app.plugins.plugin_registry import PluginRegistry
    from app.plugins.plugin_runner import PluginRunner

    for case in (source, related):
        session.add(
            Entity(
                case_id=case.id,
                entity_type="person",
                data={"first_name": "Shared", "last_name": "Name"},
                created_by_id=initiator.id,
            )
        )
    session.commit()
    ctx = PluginRun.for_test(
        session=session,
        user=initiator,
        api_keys={},
        evidence=[],
        entities=[],
        case_id=source.id,
        save_to_case=True,
    )
    ctx = replace(ctx, evidence=ServiceEvidenceSink(session))
    events = [
        event
        async for event in PluginRunner(
            PluginRegistry.from_classes([CorrelationScan])
        ).run("CorrelationScan", {}, ctx)
    ]
    assert not any(event.kind == "error" for event in events), events


import pytest


@pytest.mark.asyncio
async def test_saved_report_requires_every_case_and_keeps_original_bytes(
    client,
    session,
    test_case,
    test_admin,
    test_user,
    tmp_path,
    monkeypatch,
):
    import zipfile

    from app.core import file_storage
    from app.services import evidence_service
    from app.services.evidence_service import EvidenceService
    from app.services.export_service import ExportService

    monkeypatch.setattr(evidence_service, "UPLOAD_DIR", file_storage.UPLOAD_DIR)
    related = Case(case_number="SECRET", title="SECRET")
    session.add(related)
    session.flush()
    source_link = CaseUserLink(case_id=test_case.id, user_id=test_user.id)
    related_link = CaseUserLink(case_id=related.id, user_id=test_user.id)
    session.add_all([source_link, related_link])
    session.commit()
    await save_scan(session, test_case, related, test_admin)
    service = EvidenceService(session)
    report = next(
        item
        for item in await service.get_case_evidence(test_case.id, test_admin)
        if not item.is_folder
    )
    app.dependency_overrides[get_current_user] = lambda: test_user
    url = f"/api/evidence/{report.id}"
    downloaded = client.get(url + "/download")
    assert downloaded.headers["cache-control"] == "private, no-store"
    original = downloaded.content
    assert b"SECRET" in original
    original_hash = client.get(url).json()["file_hash"]
    assert (
        client.put(
            url, json={"title": "Renamed report", "description": "Updated"}
        ).status_code
        == 200
    )
    session.delete(related_link)
    session.commit()
    for suffix in ("", "/download", "/content", "/metadata"):
        assert client.get(url + suffix).status_code == 403
    for suffix in ("", "/folder-tree"):
        listing = client.get(f"/api/evidence/case/{test_case.id}" + suffix).json()
        assert all(item["id"] != report.id for item in listing)
    bundle = ExportService(session).export_case_bundle(test_case.id, test_user)
    try:
        with zipfile.ZipFile(bundle.path) as archive:
            assert all(
                b"SECRET" not in archive.read(name) for name in archive.namelist()
            )
    finally:
        bundle.path.unlink()
    app.dependency_overrides[get_current_user] = lambda: test_admin
    assert client.get(url + "/download").content == original
    assert client.get(url).json()["file_hash"] == original_hash


@pytest.mark.parametrize("verified", [False, True])
def test_legacy_report_receipts_and_protection_survive_metadata_edits(
    client,
    session,
    test_case,
    test_admin,
    test_user,
    verified,
):
    from uuid import uuid4

    from app.database.models import Evidence, ExecutionEffect

    related = Case(case_number="SECRET", title="SECRET")
    session.add(related)
    session.flush()
    session.add(CaseUserLink(case_id=test_case.id, user_id=test_user.id))
    url = retain(session, test_case, test_admin, [group(test_case, related, "SECRET")])
    execution_id = int(url.rsplit("/", 1)[1])
    from sqlmodel import select

    execution = session.get(PluginExecution, execution_id)
    execution.save_to_case = True
    control = session.exec(
        select(ExecutionControl).where(
            ExecutionControl.plugin_execution_id == execution_id
        )
    ).one()
    artifact = f"{control.id}-{uuid4()}"
    session.add(
        ExecutionEffect(
            control_id=control.id,
            operation_id="plugin:evidence:0",
            artifact_id=artifact,
        )
    )
    report = Evidence(
        case_id=test_case.id,
        created_by_id=test_admin.id,
        evidence_type="file",
        title="Correlation Scan results.txt",
        description="Output generated by Correlation Scan plugin",
        content=(
            f"{test_case.id}/.execution-artifacts/{artifact}.txt"
            if verified
            else "old/CorrelationScan_results.txt"
        ),
    )
    session.add(report)
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: test_admin
    path = f"/api/evidence/{report.id}"
    assert (
        client.put(
            path,
            json={
                "title": "Ordinary report",
                "description": "Ordinary",
                "correlation_case_ids": [],
            },
        ).status_code
        == 200
    )
    app.dependency_overrides[get_current_user] = lambda: test_user
    assert client.get(path).status_code == 403
    session.add(CaseUserLink(case_id=related.id, user_id=test_user.id))
    session.commit()
    assert client.get(path).status_code == (200 if verified else 403)
    app.dependency_overrides[get_current_user] = lambda: test_admin
    assert client.get(path).status_code == 200


def test_notices_errors_missing_cases_and_legacy_summaries_do_not_disclose(
    client,
    session,
    test_case,
    test_admin,
    test_user,
):
    related = Case(case_number="SECRET", title="SECRET")
    session.add(related)
    session.flush()
    session.add_all(
        [
            CaseUserLink(case_id=test_case.id, user_id=test_user.id),
            CaseUserLink(case_id=related.id, user_id=test_user.id),
        ]
    )
    related_id = related.id
    events = [
        group(test_case, related, "SECRET"),
        {"type": "status", "data": {"message": "SECRET", "case_scope": [related.id]}},
        {"type": "status", "data": {"message": "SECRET unscoped"}},
        {"type": "error", "data": {"message": "SECRET error"}},
        {
            "type": "data",
            "data": {
                "message": "Source reference skipped",
                "case_scope": [test_case.id],
            },
        },
        {"type": "complete", "data": {"message": "SECRET summary"}},
    ]
    url = retain(session, test_case, test_admin, events)
    session.delete(related)
    session.commit()
    # SQLite leaves the historical membership behind: existence still matters.
    assert related_id is not None
    app.dependency_overrides[get_current_user] = lambda: test_user
    response = client.get(url + "/results")
    assert "SECRET" not in response.text
    assert "Source reference skipped" in response.text
    assert "partial" in response.text


@pytest.mark.asyncio
async def test_new_explanations_and_warning_only_cases_remain_protected(
    client,
    session,
    test_case,
    test_admin,
    test_user,
    monkeypatch,
):
    from dataclasses import replace

    from app.core import file_storage
    from app.plugins.base_plugin import PluginRun
    from app.plugins.correlation_plugin import CorrelationScan
    from app.plugins.plugin_context import ServiceEvidenceSink
    from app.plugins.plugin_registry import PluginRegistry
    from app.plugins.plugin_runner import PluginRunner
    from app.schemas.entity_schema import EntityCreate
    from app.services import evidence_service
    from app.services.entity_service import EntityService
    from app.services.evidence_service import EvidenceService

    monkeypatch.setattr(evidence_service, "UPLOAD_DIR", file_storage.UPLOAD_DIR)
    related = Case(case_number="RELATED", title="Related")
    warning_case = Case(case_number="WARNING", title="Warning only")
    session.add_all([related, warning_case])
    session.flush()
    session.add_all(
        [
            CaseUserLink(case_id=case.id, user_id=test_user.id)
            for case in (test_case, related)
        ]
    )
    session.commit()
    service = EntityService(session)
    for case, data in (
        (test_case, {"email": "ada@example.com"}),
        (related, {"email": "charles@example.com"}),
        (
            warning_case,
            {"first_name": "Warning only", "usernames": ["https://[broken"]},
        ),
    ):
        await service.create_entity(
            case.id, EntityCreate(entity_type="person", data=data), test_admin
        )
    ctx = replace(
        PluginRun.for_test(
            session=session,
            user=test_admin,
            api_keys={},
            evidence=[],
            entities=[],
            case_id=test_case.id,
            save_to_case=True,
        ),
        evidence=ServiceEvidenceSink(session),
    )
    events = [
        event
        async for event in PluginRunner(
            PluginRegistry.from_classes([CorrelationScan])
        ).run("CorrelationScan", {}, ctx)
    ]
    assert not any(event.kind == "error" for event in events)
    url = retain(session, test_case, test_admin, [event.to_wire() for event in events])
    report = next(
        item
        for item in await EvidenceService(session).get_case_evidence(
            test_case.id, test_admin
        )
        if not item.is_folder
    )
    report_url = f"/api/evidence/{report.id}/download"
    app.dependency_overrides[get_current_user] = lambda: test_user
    visible = client.get(url + "/results").json()["items"]
    visible = [event for event in visible if "matches" in event["data"]]
    assert visible[0]["data"]["source_fields"] == [
        {"field": "email", "value": "ada@example.com"}
    ]
    assert visible[0]["data"]["matches"][0]["fields"] == [
        {"field": "email", "value": "charles@example.com"}
    ]
    assert visible[0]["data"]["matches"][0]["signal"] == "Shared domain association"
    assert "skipped_reference" not in str(visible)
    assert client.get(report_url).status_code == 403
    warning_link = CaseUserLink(case_id=warning_case.id, user_id=test_user.id)
    session.add(warning_link)
    session.commit()
    assert "skipped_reference" in str(client.get(url + "/results").json())
    original = client.get(report_url)
    assert original.status_code == 200
    assert b"coverage is incomplete" in original.content
    session.delete(warning_link)
    session.commit()
    assert client.get(report_url).status_code == 403


def test_hunt_consumers_inherit_verified_skipped_reference_scope(
    client, session, test_case, test_admin, test_user
):
    from app.database.models import Hunt, HuntExecution, HuntStep

    related = Case(case_number="WARNING", title="Warning only")
    session.add(related)
    session.flush()
    related_link = CaseUserLink(case_id=related.id, user_id=test_user.id)
    session.add_all(
        [related_link, CaseUserLink(case_id=test_case.id, user_id=test_user.id)]
    )
    hunt = Hunt(
        name="warning-scope",
        display_name="Warning scope",
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
        status="completed",
        definition_snapshot={
            "steps": [
                {"step_id": "scan", "plugin_name": "CorrelationScan"},
                {
                    "step_id": "report",
                    "plugin_name": "OtherPlugin",
                    "parameter_mapping": {"input": "scan.results"},
                },
            ]
        },
    )
    session.add(execution)
    session.flush()
    session.add_all(
        [
            HuntStep(
                execution_id=execution.id,
                step_id="scan",
                plugin_name="CorrelationScan",
                parameters={},
                status="completed",
                output={
                    "results": [
                        {
                            "notice_type": "skipped_reference",
                            "case_id": related.id,
                            "case_scope": [test_case.id, related.id],
                            "message": "Reference coverage is incomplete.",
                        }
                    ],
                    "plugin": "CorrelationScan",
                },
            ),
            HuntStep(
                execution_id=execution.id,
                step_id="report",
                plugin_name="OtherPlugin",
                parameters={},
                status="completed",
                output={"results": [{"copied": "Warning summary"}]},
            ),
        ]
    )
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: test_user
    url = f"/api/hunts/executions/{execution.id}?include_steps=true"
    assert "Warning summary" in client.get(url).text
    session.delete(related_link)
    session.commit()
    assert "Warning summary" not in client.get(url).text


def test_continuation_metadata_and_new_signals_follow_each_parts_case_access(
    client, session, test_case, test_admin, test_analyst
):
    hidden = Case(case_number="PRIVATE", title="PRIVATE")
    visible = Case(case_number="PUBLIC", title="PUBLIC")
    session.add_all([hidden, visible])
    session.flush()
    session.add_all(
        [
            CaseUserLink(case_id=test_case.id, user_id=test_analyst.id),
            CaseUserLink(case_id=visible.id, user_id=test_analyst.id),
        ]
    )
    parts = []
    for case in (hidden, visible, visible):
        event = group(test_case, case, "Source")
        event["data"].update(
            group_id="source-only-identity",
            continuation="merge",
            match_type="email",
            normalized_value="source@example.com",
            source_fields=[{"field": "email", "value": "source@example.com"}],
        )
        event["data"]["matches"][0].update(
            signal="Exact email match",
            signal_rank=0,
            fields=[{"field": "email", "value": f"{case.title}@example.com"}],
        )
        parts.append(event)
    url = retain(session, test_case, test_admin, parts)
    app.dependency_overrides[get_current_user] = lambda: test_analyst
    first = client.get(url + "/results?limit=1").json()
    assert first["items"] == [] and first["next_cursor"] == 1
    second = client.get(url + "/results?limit=1&cursor=1").json()
    payload = second["items"][0]["data"]
    assert payload["group_id"] == "source-only-identity"
    assert payload["continuation"] == "merge"
    assert payload["matches"][0]["signal_rank"] == 0
    assert payload["matches"][0]["fields"][0]["value"] == "PUBLIC@example.com"
    assert "PRIVATE" not in str(client.get(url + "/results").json())
    app.dependency_overrides[get_current_user] = lambda: test_admin
    assert "PRIVATE@example.com" in str(client.get(url + "/results").json())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind, entity_type, field, canonical, expanded, signal",
    [
        (
            "ip_address",
            "ip_address",
            "ip_address",
            "2001:db8::1",
            "2001:0db8:0000:0000:0000:0000:0000:0001",
            "Exact IP address match",
        ),
        (
            "exact_profile",
            "person",
            "social_media.linkedin",
            "https://example.com/Ada?tag=One#Bio",
            " HTTPS://EXAMPLE.COM./Ada?tag=One#Bio ",
            "Equal recorded profile reference",
        ),
    ],
)
async def test_identifier_scan_retention_export_and_evidence_follow_membership(
    client,
    session,
    test_case,
    test_admin,
    test_user,
    monkeypatch,
    kind,
    entity_type,
    field,
    canonical,
    expanded,
    signal,
):
    from dataclasses import replace

    from app.core import file_storage
    from app.database.models import Entity
    from app.plugins.base_plugin import PluginRun
    from app.plugins.correlation_plugin import CorrelationScan
    from app.plugins.plugin_context import ServiceEvidenceSink
    from app.plugins.plugin_registry import PluginRegistry
    from app.plugins.plugin_runner import PluginRunner
    from app.services import evidence_service
    from app.services.evidence_service import EvidenceService

    monkeypatch.setattr(evidence_service, "UPLOAD_DIR", file_storage.UPLOAD_DIR)
    related = Case(case_number="IP-RELATED", title="Related IP")
    hidden = Case(case_number="IP-HIDDEN", title="Hidden IP")
    session.add_all([related, hidden])
    session.flush()
    related_link = CaseUserLink(case_id=related.id, user_id=test_user.id)
    session.add_all(
        [CaseUserLink(case_id=test_case.id, user_id=test_user.id), related_link]
    )
    for case, raw in (
        (test_case, canonical),
        (related, expanded),
        (hidden, canonical),
    ):
        session.add(
            Entity(
                case_id=case.id,
                entity_type=entity_type,
                data=(
                    {"ip_address": raw}
                    if kind == "ip_address"
                    else {
                        "first_name": f"Person {case.id}",
                        "social_media": {"linkedin": raw},
                    }
                ),
                created_by_id=test_admin.id,
            )
        )
    session.commit()
    ctx = replace(
        PluginRun.for_test(
            session=session,
            user=test_admin,
            api_keys={},
            evidence=[],
            entities=[],
            case_id=test_case.id,
            save_to_case=True,
        ),
        evidence=ServiceEvidenceSink(session),
    )
    events = [
        event
        async for event in PluginRunner(
            PluginRegistry.from_classes([CorrelationScan])
        ).run("CorrelationScan", {}, ctx)
    ]
    assert not any(event.kind == "error" for event in events)
    url = retain(session, test_case, test_admin, [event.to_wire() for event in events])
    report = next(
        item
        for item in await EvidenceService(session).get_case_evidence(
            test_case.id, test_admin
        )
        if not item.is_folder
    )
    report_url = f"/api/evidence/{report.id}/download"
    app.dependency_overrides[get_current_user] = lambda: test_user
    # The standalone export reads these same authorized result pages.
    visible = client.get(url + "/results").json()["items"]
    groups = [event["data"] for event in visible if "matches" in event["data"]]
    assert len(groups) == 1
    assert groups[0]["match_type"] == kind
    assert groups[0]["source_fields"] == [{"field": field, "value": canonical}]
    assert groups[0]["matches"][0]["fields"] == [{"field": field, "value": expanded}]
    assert [match["case_id"] for match in groups[0]["matches"]] == [related.id]
    assert "Hidden IP" not in str(visible)
    assert client.get(report_url).status_code == 403
    hidden_link = CaseUserLink(case_id=hidden.id, user_id=test_user.id)
    session.add(hidden_link)
    session.commit()
    authorized = client.get(url + "/results").json()["items"]
    assert sum(len(event["data"].get("matches", [])) for event in authorized) == 2
    downloaded = client.get(report_url)
    assert downloaded.is_success
    for text in (
        signal,
        f"Match Type: {kind}",
        expanded,
        "Hidden IP",
        "Related IP",
        "Total matches: 2",
    ):
        assert text in downloaded.text
    session.delete(related_link)
    session.commit()
    after = client.get(url + "/results").json()["items"]
    assert "Related IP" not in str(after)
    assert expanded not in str(after)
    assert client.get(report_url).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: test_admin
    assert client.get(report_url).content == downloaded.content
