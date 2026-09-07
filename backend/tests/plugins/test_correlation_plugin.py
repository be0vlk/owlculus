"""Correlation behavior through accepted Entities and the PluginRunner boundary."""

import pytest

from app.database.models import Case
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
    assert forward[0]["entity_name"] == f"Person #{person.id}"
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
        {"field": "domain", "value": " Example.COM. "}
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
        events[0].payload["executed_at"],
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
        await entity(session, test_admin, case, "person")
        await entity(session, test_admin, case, "vehicle")
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
    await entity(session, test_admin, cases[0], "person", usernames=[reference])
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
