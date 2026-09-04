"""Correlation plugin contract tests."""

import pytest

from app.database.models import Case, Entity
from app.plugins.base_plugin import PluginRun, ResultEvent
from app.plugins.correlation_plugin import CorrelationScan


def context(session, user):
    return PluginRun.for_test(
        session=session,
        user=user,
        api_keys={},
        evidence=[],
        entities=[],
        case_id=1,
    )


@pytest.mark.asyncio
async def test_case_id_is_required(session, test_admin):
    events = [
        event async for event in CorrelationScan().run({}, context(session, test_admin))
    ]

    assert events == [ResultEvent.error("Parameters are required")]


@pytest.mark.asyncio
async def test_inaccessible_case_is_reported_through_context_session(
    session, test_analyst
):
    events = [
        event
        async for event in CorrelationScan().run(
            {"case_id": 999_999}, context(session, test_analyst)
        )
    ]

    assert events == [ResultEvent.error("You do not have access to this case")]


@pytest.mark.asyncio
async def test_admin_scan_with_no_entities_has_no_findings(session, test_admin):
    events = [
        event
        async for event in CorrelationScan().run(
            {"case_id": 999_999}, context(session, test_admin)
        )
    ]

    assert events == []


@pytest.mark.asyncio
async def test_admin_scan_emits_a_real_cross_case_name_match(
    session, test_admin, test_case
):
    other_case = Case(case_number="CORR-OTHER", title="Other investigation")
    session.add(other_case)
    session.flush()
    session.add_all(
        [
            Entity(
                case_id=test_case.id,
                entity_type="person",
                data={"first_name": "Ada", "last_name": "Lovelace"},
                created_by_id=test_admin.id,
            ),
            Entity(
                case_id=other_case.id,
                entity_type="person",
                data={"first_name": "Ada", "last_name": "Lovelace"},
                created_by_id=test_admin.id,
            ),
        ]
    )
    session.commit()

    events = [
        event
        async for event in CorrelationScan().run(
            {"case_id": test_case.id}, context(session, test_admin)
        )
    ]

    assert len(events) == 1
    assert events[0].kind == "data"
    assert events[0].payload["match_type"] == "name"
    assert events[0].payload["entity_name"] == "Ada Lovelace"
    assert events[0].payload["matches"][0]["case_title"] == "Other investigation"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("analyst@Example.COM", "example.com"),
        ("https://Example.COM/profile", "example.com"),
        ("not a domain", None),
    ],
)
def test_domain_matching_normalizes_supported_identifiers(value, expected):
    assert CorrelationScan()._parse_domain_from_string(value) == expected


def test_evidence_formatter_receives_payloads():
    content = CorrelationScan().format_evidence(
        [
            {
                "entity_name": "Ada Lovelace",
                "entity_type": "person",
                "match_type": "name",
                "matches": [
                    {
                        "case_title": "Other case",
                        "case_number": "C-2",
                        "case_id": 2,
                    }
                ],
            }
        ],
        {"case_id": 1},
    )

    assert "Ada Lovelace" in content
    assert "Other case" in content
