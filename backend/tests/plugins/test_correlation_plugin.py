"""Correlation behavior through accepted Entities and the PluginRunner boundary."""

import pytest

from app.database.models import Case, Entity
from app.plugins.base_plugin import PluginRun
from app.plugins.correlation_plugin import CorrelationScan
from app.plugins.plugin_registry import PluginRegistry
from app.plugins.plugin_runner import PluginRunner
from app.schemas.entity_schema import EntityCreate
from app.services.entity_service import EntityService


async def entity(session, user, case, kind, **data):
    return await EntityService(session).create_entity(
        case.id, EntityCreate(entity_type=kind, data=data), user
    )


async def scan(session, user, case):
    ctx = PluginRun.for_test(
        session=session,
        user=user,
        api_keys={},
        evidence=[],
        entities=[],
        case_id=case.id,
    )
    events = [
        event
        async for event in PluginRunner(
            PluginRegistry.from_classes([CorrelationScan])
        ).run("CorrelationScan", {}, ctx)
    ]
    assert not [event for event in events if event.kind == "error"], events
    return [event.payload for event in events if event.kind == "data"]


@pytest.fixture
def cases(session):
    cases = [
        Case(case_number="SCAN-A", title="Source investigation"),
        Case(case_number="SCAN-B", title="Related investigation"),
    ]
    session.add_all(cases)
    session.commit()
    return cases


@pytest.mark.asyncio
async def test_unnamed_person_and_domain_connect_in_both_directions(
    session, test_admin, cases
):
    source, other = cases
    person = await entity(
        session, test_admin, source, "person", email="ada@example.com"
    )
    domain = await entity(session, test_admin, other, "domain", domain=" Example.COM. ")
    forward = await scan(session, test_admin, source)
    backward = await scan(session, test_admin, other)
    assert len(forward) == len(backward) == 1
    assert forward[0]["entity_id"] == person.id
    assert forward[0]["entity_name"] == "ada@example.com"
    assert forward[0]["matches"][0]["entity_id"] == domain.id
    assert backward[0]["matches"][0]["entity_id"] == person.id
    assert (
        forward[0]["normalized_value"]
        == backward[0]["normalized_value"]
        == "example.com"
    )
    assert forward[0]["source_fields"] == [
        {"field": "email", "value": "ada@example.com"}
    ]
    assert forward[0]["matches"][0]["fields"] == [
        {"field": "domain", "value": "example.com"}
    ]


@pytest.mark.asyncio
async def test_references_survive_malformed_urls_and_preserve_each_source(
    session, test_admin, cases
):
    source, other = cases
    ada = await entity(
        session,
        test_admin,
        source,
        "person",
        first_name="Ada",
        employer=" Engines ",
        email="ada@example.com",
        usernames=["https://[broken", "https://EXAMPLE.com/@ada", "plainusername"],
    )
    grace = await entity(
        session, test_admin, source, "person", first_name="Grace", employer="engines"
    )
    charles = await entity(
        session, test_admin, other, "person", first_name="Charles", employer="ENGINES"
    )
    company = await entity(
        session, test_admin, other, "company", name="Example", website="example.com"
    )
    for case in cases:
        await entity(session, test_admin, case, "ip_address", ip_address="192.0.2.1")
    results = await scan(session, test_admin, source)
    employers = [group for group in results if group.get("match_type") == "employer"]
    assert {group["entity_id"] for group in employers} == {ada.id, grace.id}
    assert all(
        [match["entity_id"] for match in group["matches"]] == [charles.id]
        for group in employers
    )
    domain = next(group for group in results if group.get("match_type") == "domain")
    assert [match["entity_id"] for match in domain["matches"]] == [company.id]
    assert domain["source_fields"] == [
        {"field": "email", "value": "ada@example.com"},
        {"field": "usernames[1]", "value": "https://EXAMPLE.com/@ada"},
    ]
    assert any(group.get("entity_type") == "ip_address" for group in results)
    notice = next(
        group for group in results if group.get("notice_type") == "skipped_reference"
    )
    assert notice["case_scope"] == [source.id]
    assert notice["entity_id"] == ada.id
    assert "incomplete" in notice["message"]
    assert "[broken" not in str(results)
    reverse = await scan(session, test_admin, other)
    reverse_domain = next(
        group for group in reverse if group.get("match_type") == "domain"
    )
    assert reverse_domain["matches"][0]["fields"] == domain["source_fields"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source_data,other_data,kinds,qualification",
    [
        ({"vin": " abc123 "}, {"vin": "ABC123"}, ["vin"], "Exact VIN"),
        (
            {"license_plate": "OWL-123"},
            {"license_plate": "owl 123"},
            ["license_plate"],
            "Tentative",
        ),
        (
            {"license_plate": "OWL-123", "registration_state": "CA"},
            {"license_plate": "owl 123", "registration_state": "NY"},
            [],
            None,
        ),
        (
            {"license_plate": "OWL-123", "registration_state": " ca ", "vin": "FIRST"},
            {"license_plate": "owl 123", "registration_state": "CA", "vin": "SECOND"},
            ["license_plate"],
            "conflicting VINs",
        ),
        (
            {"license_plate": "OWL-123", "registration_state": "CA", "vin": "SAME"},
            {"license_plate": "owl 123", "registration_state": "NY", "vin": "SAME"},
            ["vin"],
            "Exact VIN",
        ),
    ],
)
async def test_vehicle_identifiers_are_independent_and_honestly_qualified(
    session, test_admin, cases, source_data, other_data, kinds, qualification
):
    for case, data in zip(cases, (source_data, other_data)):
        await entity(session, test_admin, case, "vehicle", **data)
    for case in cases:
        results = await scan(session, test_admin, case)
        assert [group["match_type"] for group in results] == kinds
        if qualification:
            assert qualification in results[0]["matches"][0]["signal"]


@pytest.mark.asyncio
async def test_saved_report_preserves_explanations_counts_time_and_warning_scope(
    client, session, test_admin, cases, monkeypatch
):
    from dataclasses import replace

    from app.core import file_storage
    from app.plugins.plugin_context import ServiceEvidenceSink
    from app.services import evidence_service
    from app.services.evidence_service import EvidenceService

    monkeypatch.setattr(evidence_service, "UPLOAD_DIR", file_storage.UPLOAD_DIR)
    source, other = cases
    ada = await entity(
        session,
        test_admin,
        source,
        "person",
        first_name="Ada",
        employer="Engines",
        email="ada@example.com",
    )
    charles = await entity(
        session,
        test_admin,
        other,
        "person",
        first_name="Charles",
        employer="engines",
        email="charles@example.com",
        usernames=["https://[broken"],
    )
    ctx = replace(
        PluginRun.for_test(
            session=session,
            user=test_admin,
            api_keys={},
            evidence=[],
            entities=[],
            case_id=source.id,
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
    assert not [event for event in events if event.kind == "error"]
    report = next(
        item
        for item in await EvidenceService(session).get_case_evidence(
            source.id, test_admin
        )
        if not item.is_folder
    )
    from app.core.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: test_admin
    response = client.get(f"/api/evidence/{report.id}/download")
    assert response.status_code == 200
    text = response.content.decode()
    for expected in (
        "Total entities with matches: 1",
        "Total matches: 2",
        "Related Cases: 1",
        "Engines",
        "Ada",
        "Charles",
        "email: ada@example.com",
        "email: charles@example.com",
        "employer: engines",
        "Source investigation",
        "Related investigation",
        f"Entity ID: {ada.id}",
        f"Entity ID: {charles.id}",
        "incomplete",
        next(event.payload["executed_at"] for event in events if event.kind == "data"),
    ):
        assert expected in text
    assert "[broken" not in text
    assert report.file_hash == file_storage.calculate_file_hash(response.content)


@pytest.mark.asyncio
async def test_names_blank_entities_and_identical_domains(session, test_admin, cases):
    for case, first, last, domain in (
        (cases[0], " Ada ", "Lovelace ", " Example.COM. "),
        (cases[1], "ada", "lovelace", "example.com"),
    ):
        await entity(
            session, test_admin, case, "person", first_name=first, last_name=last
        )
        # Historical blank records remain readable and harmless to correlation.
        session.add_all(
            [
                Entity(
                    case_id=case.id,
                    entity_type=kind,
                    data={},
                    created_by_id=test_admin.id,
                )
                for kind in ("person", "vehicle")
            ]
        )
        session.commit()
        await entity(session, test_admin, case, "domain", domain=domain)
    for case in cases:
        results = await scan(session, test_admin, case)
        assert len(results) == 2
        assert all(group["match_type"] == "name" for group in results)
        assert {group["normalized_value"] for group in results} == {
            "ada lovelace",
            "example.com",
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reference,connects,skipped",
    [
        (
            " https://user:password@EXAMPLE.com./@grace?email=other@elsewhere.com#@another.com ",
            True,
            False,
        ),
        ("HTTPS://example.com/@grace", True, False),
        ("grace@EXAMPLE.com.", True, False),
        ("https://sub.example.com/@grace", False, False),
        ("example.com", False, False),
        ("https://[broken", False, True),
        ("https://example.com:bad", False, True),
        ("https://bad host.com", False, True),
    ],
)
async def test_profile_hostname_parsing_is_conservative(
    session, test_admin, cases, reference, connects, skipped
):
    await entity(
        session,
        test_admin,
        cases[0],
        "person",
        first_name="Profile subject",
        usernames=[reference],
    )
    await entity(session, test_admin, cases[1], "domain", domain="example.com")
    results = await scan(session, test_admin, cases[0])
    assert any(group.get("match_type") == "domain" for group in results) is connects
    assert (
        any(group.get("notice_type") == "skipped_reference" for group in results)
        is skipped
    )


@pytest.mark.asyncio
async def test_persisted_legacy_network_assets_keep_their_name_connection(
    session, test_admin, cases
):
    from app.database.models import Entity

    for case in cases:
        session.add(
            Entity(
                case_id=case.id,
                created_by_id=test_admin.id,
                entity_type="network_assets",
                data={"domains": ["legacy.example.com"]},
            )
        )
    session.commit()
    result = await scan(session, test_admin, cases[0])
    assert len(result) == 1
    assert result[0]["match_type"] == "name"
    assert result[0]["source_fields"] == [
        {"field": "domains[0]", "value": "legacy.example.com"}
    ]


@pytest.mark.asyncio
async def test_exact_email_is_separate_from_domain_and_preserves_local_part(
    session, test_admin, cases
):
    await entity(session, test_admin, cases[0], "person", email="Ada+tag@gmail.com")
    exact = await entity(
        session,
        test_admin,
        cases[1],
        "person",
        first_name="Other",
        email="Ada+tag@GMAIL.COM",
    )
    for address in ("ada+tag@gmail.com", "Ada@gmail.com", "A.da+tag@gmail.com"):
        await entity(session, test_admin, cases[1], "person", email=address)
    results = await scan(session, test_admin, cases[0])
    assert results[0]["match_type"] == "email"
    assert [match["entity_id"] for match in results[0]["matches"]] == [exact.id]
    assert results[0]["source_fields"] == [
        {"field": "email", "value": "Ada+tag@gmail.com"}
    ]
    assert results[0]["matches"][0]["signal"] == "Exact email match"
    domain = next(group for group in results if group.get("match_type") == "domain")
    assert len(domain["matches"]) == 4
    assert "low signal" in domain["matches"][-1]["signal"].lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "other_phone,connects,skipped",
    [
        ("+1 202.555-0123", True, False),
        ("1 202 555 0123", False, False),
        ("2025550123", False, False),
        ("+1 202 555 0123 ext 4", False, True),
        ("+1 202 555 0123#4", False, True),
        ("call +1 202 555 0123", False, True),
    ],
)
async def test_phone_matching_is_conservative_and_cross_type(
    session, test_admin, cases, other_phone, connects, skipped
):
    await entity(session, test_admin, cases[0], "person", phone="+1 (202) 555-0123")
    await entity(session, test_admin, cases[1], "company", name="", phone=other_phone)
    for case in cases:
        results = await scan(session, test_admin, case)
        groups = [row for row in results if row.get("match_type") == "phone"]
        assert bool(groups) is connects
        assert (
            any(row.get("notice_type") == "skipped_reference" for row in results)
            is skipped
        )
        if connects:
            assert groups[0]["normalized_value"] == "+12025550123"
            assert groups[0]["matches"][0]["signal"] == "Exact phone match"
            assert groups[0]["source_fields"][0]["value"] in (
                other_phone,
                "+1 (202) 555-0123",
            )


@pytest.mark.asyncio
async def test_large_group_is_losslessly_continued_with_report_counts(
    session, test_admin, cases, monkeypatch
):
    from app.plugins.output_limits import serialized_size

    monkeypatch.setenv("EXECUTION_EVENT_LIMIT_BYTES", "2400")
    await entity(session, test_admin, cases[0], "person", employer="Popular")
    related = [
        await entity(
            session,
            test_admin,
            cases[1],
            "person",
            first_name=f"Person {index}",
            employer="Popular",
        )
        for index in range(12)
    ]
    evidence = []
    ctx = PluginRun.for_test(
        session=session,
        user=test_admin,
        api_keys={},
        evidence=evidence,
        entities=[],
        case_id=cases[0].id,
        save_to_case=True,
    )
    events = [
        event
        async for event in PluginRunner(
            PluginRegistry.from_classes([CorrelationScan])
        ).run("CorrelationScan", {}, ctx)
    ]
    assert not [event for event in events if event.kind == "error"], events
    parts = [
        event.payload
        for event in events
        if event.kind == "data" and "matches" in event.payload
    ]
    assert len(parts) > 1
    assert len({part["group_id"] for part in parts}) == 1
    assert all(part["continuation"] == "merge" for part in parts)
    assert all(serialized_size(event.to_wire()) <= 2400 for event in events)
    assert [match["entity_id"] for part in parts for match in part["matches"]] == [
        row.id for row in related
    ]
    assert "Total entities with matches: 1" in evidence[0].content
    assert "Total matches: 12" in evidence[0].content
    assert evidence[0].content.count("Match Type: employer") == 1


@pytest.mark.asyncio
async def test_common_provider_overlap_is_last_but_explicit_domain_is_not_downgraded(
    session, test_admin, cases
):
    first = await entity(
        session, test_admin, cases[0], "person", email="first@gmail.com"
    )
    await entity(session, test_admin, cases[0], "person", employer="Specific")
    await entity(
        session,
        test_admin,
        cases[1],
        "person",
        email="second@gmail.com",
        employer="Specific",
    )
    groups = await scan(session, test_admin, cases[0])
    assert [group["match_type"] for group in groups] == ["employer", "domain"]
    domain = await entity(session, test_admin, cases[1], "domain", domain="gmail.com")
    groups = await scan(session, test_admin, cases[0])
    visible = [
        match
        for group in groups
        if group.get("entity_id") == first.id
        for match in group["matches"]
    ]
    assert visible[0]["entity_id"] == domain.id
    assert visible[0]["signal_rank"] == 1
    assert "Low signal" not in visible[0]["signal"]
    assert visible[-1]["signal_rank"] == 2
    reverse = await scan(session, test_admin, cases[1])
    explicit = next(group for group in reverse if group.get("entity_id") == domain.id)
    assert explicit["matches"][0]["signal_rank"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("operation_limit,huge_value", [(4200, False), (20000, True)])
async def test_scan_limits_keep_accepted_prefix_and_never_save_a_complete_report(
    session, test_admin, cases, monkeypatch, operation_limit, huge_value
):
    monkeypatch.setenv("EXECUTION_EVENT_LIMIT_BYTES", "2400")
    monkeypatch.setenv("EXECUTION_RESULT_LIMIT_BYTES", str(operation_limit))
    await entity(session, test_admin, cases[0], "person", employer="Popular")
    for index in range(12):
        await entity(
            session,
            test_admin,
            cases[1],
            "person",
            first_name=(
                "x" * 3000 if huge_value and index == 11 else f"Related {index}"
            ),
            employer="Popular",
        )
    evidence = []
    ctx = PluginRun.for_test(
        session=session,
        user=test_admin,
        api_keys={},
        evidence=evidence,
        entities=[],
        case_id=cases[0].id,
        save_to_case=True,
    )
    events = [
        event
        async for event in PluginRunner(
            PluginRegistry.from_classes([CorrelationScan])
        ).run("CorrelationScan", {}, ctx)
    ]
    retained = [
        match
        for event in events
        if event.kind == "data"
        for match in event.payload.get("matches", [])
    ]
    assert 0 < len(retained) < 12
    assert len({match["entity_id"] for match in retained}) == len(retained)
    assert events[-2].kind == "error"
    assert events[-2].payload["partial"] is True
    assert events[-2].payload["code"] == (
        "event_size_limit" if huge_value else "result_size_limit"
    )
    assert events[-1].kind == "complete"
    assert evidence == []


@pytest.mark.asyncio
@pytest.mark.parametrize("stop", ["cancel", "deadline"])
async def test_stop_during_continuation_retains_prefix_without_completion_or_evidence(
    session, test_admin, cases, monkeypatch, stop
):
    import asyncio

    monkeypatch.setenv("EXECUTION_EVENT_LIMIT_BYTES", "2400")
    await entity(session, test_admin, cases[0], "person", employer="Popular")
    for index in range(12):
        await entity(
            session,
            test_admin,
            cases[1],
            "person",
            first_name=f"Related {index}",
            employer="Popular",
        )
    evidence, accepted = [], []
    ctx = PluginRun.for_test(
        session=session,
        user=test_admin,
        api_keys={},
        evidence=evidence,
        entities=[],
        case_id=cases[0].id,
        save_to_case=True,
    )

    async def consume():
        async with asyncio.timeout(None) as deadline:
            async for event in PluginRunner(
                PluginRegistry.from_classes([CorrelationScan])
            ).run("CorrelationScan", {}, ctx):
                accepted.append(event)
                if event.kind == "data":
                    if stop == "cancel":
                        asyncio.current_task().cancel()
                    else:
                        deadline.reschedule(asyncio.get_running_loop().time())

    task = asyncio.create_task(consume())
    with pytest.raises(asyncio.CancelledError if stop == "cancel" else TimeoutError):
        await task
    retained = [
        match
        for event in accepted
        if event.kind == "data"
        for match in event.payload["matches"]
    ]
    assert 0 < len(retained) < 12
    assert not any(event.kind == "complete" for event in accepted)
    assert not evidence


@pytest.mark.asyncio
async def test_provider_overlap_stays_low_signal_with_additional_profile_fields(
    session, test_admin, cases
):
    for case, local in zip(cases, ("ada", "charles")):
        await entity(
            session,
            test_admin,
            case,
            "person",
            email=f"{local}@gmail.com",
            usernames=[f"https://gmail.com/@{local}"],
        )
    results = await scan(session, test_admin, cases[0])
    assert len(results) == 1
    assert results[0]["matches"][0]["signal_rank"] == 2
    assert "Low signal" in results[0]["matches"][0]["signal"]
    assert len(results[0]["source_fields"]) == 2
    assert len(results[0]["matches"][0]["fields"]) == 2


@pytest.mark.asyncio
async def test_legacy_malformed_email_does_not_become_an_exact_identifier(
    session, test_admin, cases
):
    from app.database.models import Entity

    # Legacy stored data can predate current EmailStr input validation.
    for case in cases:
        session.add(
            Entity(
                case_id=case.id,
                created_by_id=test_admin.id,
                entity_type="person",
                data={"email": "https://example.com/profile", "employer": "Shared"},
            )
        )
    session.commit()
    results = await scan(session, test_admin, cases[0])
    assert [row["match_type"] for row in results if "matches" in row] == ["employer"]
    warnings = [row for row in results if row.get("notice_type") == "skipped_reference"]
    assert len(warnings) == 2
    assert all(row["field"] == "email" for row in warnings)


@pytest.mark.asyncio
async def test_historical_hostname_identity_and_local_warnings(
    session, test_admin, cases
):
    from app.database.models import Entity

    source, other = cases
    raw_entities = [
        Entity(
            created_by_id=test_admin.id,
            case_id=source.id,
            entity_type="company",
            data={"name": "Historical", "website": " BÜCHER.example.:8080/path?q=1#f "},
        ),
        Entity(
            created_by_id=test_admin.id,
            case_id=other.id,
            entity_type="domain",
            data={"domain": " XN--BCHER-KVA.EXAMPLE. "},
        ),
        Entity(
            created_by_id=test_admin.id,
            case_id=other.id,
            entity_type="person",
            data={
                "email": "Ada@bücher.example.",
                "usernames": ["HTTPS://BÜCHER.example/profile"],
            },
        ),
        Entity(
            created_by_id=test_admin.id,
            case_id=other.id,
            entity_type="domain",
            data={"domain": "shop.bücher.example"},
        ),
        Entity(
            created_by_id=test_admin.id,
            case_id=other.id,
            entity_type="company",
            data={"name": "Broken", "website": "https://http//private.example"},
        ),
        Entity(
            created_by_id=test_admin.id,
            case_id=other.id,
            entity_type="domain",
            data={"domain": "bad_label.example"},
        ),
    ]
    session.add_all(raw_entities)
    session.commit()
    results = await scan(session, test_admin, source)
    group = next(item for item in results if item.get("match_type") == "domain")
    assert group["normalized_value"] == "xn--bcher-kva.example"
    assert {item["entity_id"] for item in group["matches"]} == {
        raw_entities[1].id,
        raw_entities[2].id,
    }
    person_match = next(
        item for item in group["matches"] if item["entity_id"] == raw_entities[2].id
    )
    assert {field["field"] for field in person_match["fields"]} == {
        "email",
        "usernames[0]",
    }
    notices = [
        item for item in results if item.get("notice_type") == "skipped_reference"
    ]
    assert notices, results
    assert len(notices) == 2
    assert all(item["case_scope"] == [source.id, other.id] for item in notices)
    assert "private.example" not in str(notices)
    assert "bad_label.example" not in str(notices)


@pytest.mark.asyncio
async def test_accepted_email_hostname_identity_preserves_local_part(
    session, test_admin, cases
):
    await entity(session, test_admin, cases[0], "person", email="Ada@BÜCHER.example.")
    await entity(
        session, test_admin, cases[1], "person", email="Ada@xn--bcher-kva.example"
    )
    await entity(session, test_admin, cases[1], "person", email="ada@bücher.example")
    results = await scan(session, test_admin, cases[0])
    exact = next(item for item in results if item.get("match_type") == "email")
    assert exact["normalized_value"] == "Ada@xn--bcher-kva.example"
    assert len(exact["matches"]) == 1


@pytest.mark.asyncio
async def test_canonical_ip_matches_preserve_fields_and_skip_unsupported(
    session, test_admin, cases
):
    expanded = "2001:0DB8:0000:0000:0000:0000:0000:0001"
    old = Entity(
        case_id=cases[0].id,
        entity_type="ip_address",
        created_by_id=test_admin.id,
        data={"ip_address": expanded},
    )
    session.add(old)
    session.commit()
    new = await entity(
        session, test_admin, cases[1], "ip_address", ip_address="2001:db8::1"
    )
    for case in cases:
        for raw in ("fe80::1%eth0", "address 2001:db8::1", "2001:db8::/64"):
            session.add(
                Entity(
                    case_id=case.id,
                    entity_type="ip_address",
                    created_by_id=test_admin.id,
                    data={"ip_address": raw},
                )
            )
    session.commit()
    await entity(session, test_admin, cases[0], "ip_address", ip_address="192.0.2.1")
    await entity(
        session, test_admin, cases[1], "ip_address", ip_address="::ffff:192.0.2.1"
    )
    await entity(session, test_admin, cases[1], "ip_address", ip_address="2001:db8::2")
    for case, source, related, raw, other_raw in (
        (cases[0], old, new, expanded, "2001:db8::1"),
        (cases[1], new, old, "2001:db8::1", expanded),
    ):
        results = await scan(session, test_admin, case)
        groups = [group for group in results if "matches" in group]
        assert len(groups) == 1
        group = groups[0]
        assert group["match_type"] == "ip_address"
        assert group["entity_id"] == source.id
        assert group["normalized_value"] == "2001:db8::1"
        assert group["source_fields"] == [{"field": "ip_address", "value": raw}]
        assert group["matches"][0]["entity_id"] == related.id
        assert group["matches"][0]["fields"] == [
            {"field": "ip_address", "value": other_raw}
        ]
        assert group["matches"][0]["signal"] == "Exact IP address match"
        assert group["matches"][0]["signal_rank"] == 0
        notices = [
            group
            for group in results
            if group.get("notice_type") == "skipped_reference"
        ]
        assert len(notices) == 6
        assert all(
            notice["field"] == "ip_address" and case.id in notice["case_scope"]
            for notice in notices
        )


@pytest.mark.asyncio
async def test_employer_to_company_is_bidirectional_without_company_employer_reason(
    session, test_admin, cases
):
    person = await entity(
        session,
        test_admin,
        cases[0],
        "person",
        first_name="Ada",
        employer="  Analytical   Engines ",
    )
    company = await entity(
        session, test_admin, cases[1], "company", name="analytical engines"
    )
    colleague = await entity(
        session,
        test_admin,
        cases[1],
        "person",
        first_name="Charles",
        employer="ANALYTICAL ENGINES",
    )
    await entity(session, test_admin, cases[0], "company", name="analytical engines")
    forward = await scan(session, test_admin, cases[0])
    employers = [g for g in forward if g.get("match_type") == "employer"]
    group = next(g for g in employers if g["entity_id"] == person.id)
    assert {m["entity_id"] for m in group["matches"]} == {company.id, colleague.id}
    assert group["source_fields"] == [
        {"field": "employer", "value": "  Analytical   Engines "}
    ]
    match = next(m for m in group["matches"] if m["entity_id"] == company.id)
    assert match["fields"] == [{"field": "name", "value": "analytical engines"}]
    assert "not verified" in match["signal"]
    for g in employers:
        if g["entity_type"] == "company":
            assert all(m["entity_type"] == "person" for m in g["matches"])
    reverse = await scan(session, test_admin, cases[1])
    group = next(
        g
        for g in reverse
        if g.get("match_type") == "employer" and g["entity_id"] == company.id
    )
    assert [m["entity_id"] for m in group["matches"]] == [person.id]
    assert group["source_fields"] == match["fields"]


@pytest.mark.asyncio
async def test_exact_profiles_preserve_locations_values_and_rank(
    session, test_admin, cases
):
    raw = " HTTPS://BÜCHER.example.:8080/Ada?tag=One#Bio "
    canonical = "https://xn--bcher-kva.example:8080/Ada?tag=One#Bio"
    person = await entity(
        session,
        test_admin,
        cases[0],
        "person",
        first_name="Ada",
        social_media={"linkedin": raw, "other": canonical},
        usernames=[canonical, canonical],
    )
    company = await entity(
        session,
        test_admin,
        cases[1],
        "company",
        name="Engines",
        social_media={"linkedin": canonical, "other": raw},
    )
    account = await entity(
        session,
        test_admin,
        cases[1],
        "person",
        first_name="Account",
        usernames=[canonical, canonical],
    )
    await entity(session, test_admin, cases[1], "domain", domain="bücher.example")
    for case, source_id, related_ids in (
        (cases[0], person.id, {company.id, account.id}),
        (cases[1], company.id, {person.id}),
    ):
        results = await scan(session, test_admin, case)
        assert results[0]["match_type"] == "exact_profile"
        group = next(
            g
            for g in results
            if g.get("match_type") == "exact_profile" and g["entity_id"] == source_id
        )
        assert group["normalized_value"] == canonical
        assert {m["entity_id"] for m in group["matches"]} == related_ids
        assert len(group["matches"]) == len(related_ids)
        assert all(
            m["signal_rank"] == 0
            and "recorded profile reference" in m["signal"]
            and "ownership" in m["signal"]
            for m in group["matches"]
        )
        fields = (
            group["source_fields"]
            if case == cases[0]
            else group["matches"][0]["fields"]
        )
        assert {f["field"] for f in fields} == {
            "social_media.linkedin",
            "social_media.other",
            "usernames[0]",
            "usernames[1]",
        }
        assert {f["value"] for f in fields} == {raw, canonical}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "other",
    [
        "http://example.com/Ada?q=One#Bio",
        "https://example.com/ada?q=One#Bio",
        "https://example.com/Other?q=One#Bio",
        "https://example.com/Ada?q=Two#Bio",
        "https://example.com/Ada?q=One#Other",
        "https://example.com/Ada?q=One",
        "https://example.com/Ada",
        "Ada",
        "ftp://example.com/Ada?q=One#Bio",
        "https://example.com:bad/Ada?q=One#Bio",
        "https://[broken",
    ],
)
async def test_dedicated_profiles_do_not_infer_equivalence_or_host_matches(
    session, test_admin, cases, other
):
    await entity(
        session,
        test_admin,
        cases[0],
        "person",
        first_name="Source",
        social_media={"linkedin": "https://example.com/Ada?q=One#Bio"},
    )
    await entity(
        session,
        test_admin,
        cases[1],
        "company",
        name="Related",
        social_media={"linkedin": other},
    )
    results = await scan(session, test_admin, cases[0])
    assert not any("matches" in g for g in results)
    if other in {"https://[broken", "https://example.com:bad/Ada?q=One#Bio"}:
        assert any(g.get("field") == "social_media.linkedin" for g in results)


@pytest.mark.asyncio
@pytest.mark.parametrize("source_kind", ["empty", "unusable", "malformed"])
async def test_empty_scan_completes_with_only_source_warnings_and_provenance(
    session, test_admin, cases, source_kind
):
    if source_kind != "empty":
        session.add(
            Entity(
                case_id=cases[0].id,
                created_by_id=test_admin.id,
                entity_type="person",
                data={
                    "usernames": [
                        "https://[broken" if source_kind == "malformed" else "handle"
                    ]
                },
            )
        )
        session.commit()
    await entity(
        session,
        test_admin,
        cases[1],
        "person",
        first_name="Candidate",
        usernames=["https://[broken"],
    )
    ctx = PluginRun.for_test(
        session=session,
        user=test_admin,
        api_keys={},
        evidence=[],
        entities=[],
        case_id=cases[0].id,
    )
    events = [
        event
        async for event in PluginRunner(
            PluginRegistry.from_classes([CorrelationScan])
        ).run("CorrelationScan", {}, ctx)
    ]
    assert events[-1].kind == "complete"
    assert not any(e.kind == "error" or "matches" in e.payload for e in events)
    notices = [e.payload for e in events if e.kind == "data"]
    assert len(notices) == (1 if source_kind == "malformed" else 0)
    assert all(
        n["field"] == "usernames[0]" and n["case_scope"] == [cases[0].id]
        for n in notices
    )
    assert all(cases[1].id not in e.payload.get("case_scope", []) for e in events)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source_profile,related_profile",
    [
        ("same-handle", "same-handle"),
        ("https://example.com/Ada?", "https://example.com/Ada"),
        ("https://example.com/Ada#", "https://example.com/Ada"),
        ("https://example.com/Ada?tag=One", "https://example.com/Ada?tag=one"),
        ("https://example.com/Ada#Bio", "https://example.com/Ada#bio"),
    ],
)
async def test_profiles_do_not_equate_handles_or_discard_url_components(
    session, test_admin, cases, source_profile, related_profile
):
    for case, name, profile in (
        (cases[0], "Source", source_profile),
        (cases[1], "Related", related_profile),
    ):
        await entity(
            session,
            test_admin,
            case,
            "person",
            first_name=name,
            social_media={"other": profile},
            usernames=[profile],
        )
    results = await scan(session, test_admin, cases[0])
    assert not any(g.get("match_type") == "exact_profile" for g in results)
    assert not any(g.get("notice_type") == "skipped_reference" for g in results)
