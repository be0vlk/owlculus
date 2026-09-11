"""Behavioral tests for cross-case entity correlation."""

import pytest
from sqlmodel import Session

from app.core.exceptions import AuthorizationException
from app.database.models import Case, CaseUserLink, Entity, User
from app.services.entity_correlation import CorrelationKind, EntityCorrelation


def _case(session: Session, *, number: str, title: str, user: User) -> Case:
    case = Case(case_number=number, title=title)
    session.add(case)
    session.flush()
    session.add(CaseUserLink(case_id=case.id, user_id=user.id))
    return case


def _entity(
    session: Session,
    *,
    case: Case,
    user: User,
    entity_type: str,
    data: dict,
) -> Entity:
    entity = Entity(
        case_id=case.id,
        entity_type=entity_type,
        data=data,
        created_by_id=user.id,
    )
    session.add(entity)
    return entity


def test_correlate_returns_one_typed_name_match_for_two_seeded_cases(
    session: Session, test_user: User
) -> None:
    source_case = _case(
        session, number="CORR-001", title="Source investigation", user=test_user
    )
    other_case = _case(
        session, number="CORR-002", title="Other investigation", user=test_user
    )
    source = _entity(
        session,
        case=source_case,
        user=test_user,
        entity_type="person",
        data={"first_name": "Ada", "last_name": "Lovelace"},
    )
    other = _entity(
        session,
        case=other_case,
        user=test_user,
        entity_type="person",
        data={"first_name": "Ada", "last_name": "Lovelace"},
    )
    session.commit()

    matches = EntityCorrelation(session).correlate(source_case, test_user)

    assert len(matches) == 1
    match = matches[0]
    assert match.kind is CorrelationKind.NAME
    assert match.value == "Ada Lovelace"
    assert match.source_entity.id == source.id
    assert match.other_entity.id == other.id
    assert match.other_case.id == other_case.id


def test_correlate_uses_case_access_for_source_and_other_cases(
    session: Session, test_user: User, test_analyst: User
) -> None:
    source_case = _case(
        session, number="CORR-ACCESS-1", title="Readable", user=test_user
    )
    hidden_case = _case(
        session, number="CORR-ACCESS-2", title="Hidden", user=test_analyst
    )
    visible_case = _case(
        session, number="CORR-ACCESS-3", title="Also readable", user=test_user
    )
    for case, user in ((source_case, test_user), (hidden_case, test_analyst)):
        _entity(
            session,
            case=case,
            user=user,
            entity_type="person",
            data={"first_name": "Grace", "last_name": "Hopper"},
        )
    _entity(
        session,
        case=visible_case,
        user=test_user,
        entity_type="person",
        data={"first_name": "Katherine", "last_name": "Johnson"},
    )
    session.commit()
    session.refresh(source_case)
    session.refresh(test_user)

    assert EntityCorrelation(session).correlate(source_case, test_user) == []
    with pytest.raises(AuthorizationException):
        EntityCorrelation(session).correlate(hidden_case, test_user)


def test_correlate_returns_employer_and_domain_matches(
    session: Session, test_user: User
) -> None:
    source_case = _case(session, number="CORR-REL-1", title="Source", user=test_user)
    other_case = _case(session, number="CORR-REL-2", title="Other", user=test_user)
    _entity(
        session,
        case=source_case,
        user=test_user,
        entity_type="person",
        data={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.test",
            "employer": "Analytical Engines",
        },
    )
    _entity(
        session,
        case=other_case,
        user=test_user,
        entity_type="person",
        data={
            "first_name": "Charles",
            "last_name": "Babbage",
            "employer": "analytical engines",
        },
    )
    _entity(
        session,
        case=other_case,
        user=test_user,
        entity_type="company",
        data={"name": "Example", "website": "https://example.test/about"},
    )
    session.commit()

    matches = EntityCorrelation(session).correlate(source_case, test_user)

    assert [(match.kind, match.value) for match in matches] == [
        (CorrelationKind.DOMAIN, "example.test"),
        (CorrelationKind.EMPLOYER, "Analytical Engines"),
    ]
    assert matches[1].other_entity.data["first_name"] == "Charles"
    assert matches[0].found_in == "website: https://example.test/about"


def test_correlate_matches_employer_for_unnamed_entities(
    session: Session, test_user: User
) -> None:
    source_case = _case(
        session, number="CORR-NAMELESS-1", title="Source", user=test_user
    )
    other_case = _case(session, number="CORR-NAMELESS-2", title="Other", user=test_user)
    for case in (source_case, other_case):
        _entity(
            session,
            case=case,
            user=test_user,
            entity_type="person",
            data={"employer": "Analytical Engines"},
        )
    session.commit()

    matches = EntityCorrelation(session).correlate(source_case, test_user)
    assert [match.kind for match in matches] == [CorrelationKind.EMPLOYER]


def test_correlate_normalizes_vehicle_identifiers(
    session: Session, test_user: User
) -> None:
    source_case = _case(session, number="CORR-CAR-1", title="Source", user=test_user)
    other_case = _case(session, number="CORR-CAR-2", title="Other", user=test_user)
    source = _entity(
        session,
        case=source_case,
        user=test_user,
        entity_type="vehicle",
        data={
            "year": 2020,
            "make": "Ford",
            "model": "Transit",
            "vin": "abc123",
            "license_plate": "OWL-123",
        },
    )
    _entity(
        session,
        case=other_case,
        user=test_user,
        entity_type="vehicle",
        data={
            "year": 2021,
            "make": "Ford",
            "model": "Transit",
            "vin": "ABC123",
            "license_plate": "owl 123",
        },
    )
    session.commit()

    matches = EntityCorrelation(session).correlate(source_case, test_user)

    assert [(match.kind, match.value) for match in matches] == [
        (CorrelationKind.VIN, "ABC123"),
        (CorrelationKind.LICENSE_PLATE, "OWL-123"),
    ]
    assert all(match.source_entity.id == source.id for match in matches)
