"""Incomplete Entity input and same-Case duplicate decisions through the API."""

import pytest

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.database.models import Case
from app.main import app


@pytest.fixture
def entity_api(client, session, test_admin):
    app.dependency_overrides[get_current_user] = lambda: test_admin
    case = Case(case_number="INCOMPLETE")
    session.add(case)
    session.commit()
    return f"{settings.API_V1_STR}/cases/{case.id}/entities"


@pytest.mark.parametrize(
    "kind,data",
    [
        ("person", {}),
        ("person", {"first_name": "  ", "phone": " -- "}),
        ("person", {"social_media": {"x": "just-a-handle"}}),
        ("vehicle", {}),
        ("vehicle", {"make": "  ", "vin": " "}),
    ],
)
def test_blank_entities_rejected(client, entity_api, kind, data):
    response = client.post(entity_api, json={"entity_type": kind, "data": data})
    assert response.status_code == 422
    assert "Provide" in response.text


def test_same_name_advisory_and_separate_records(client, entity_api):
    first = client.post(
        entity_api,
        json={
            "entity_type": "person",
            "data": {
                "first_name": "Ada",
                "email": "ada@example.com",
                "dob": "1990-01-01",
            },
        },
    ).json()
    payload = {
        "entity_type": "person",
        "data": {
            "first_name": " ada ",
            "email": "other@example.com",
            "dob": "2000-01-01",
        },
    }
    advisory = client.post(f"{entity_api}/duplicate-advisories", json=payload)
    assert advisory.is_success
    assert advisory.json()[0]["id"] == first["id"]
    assert advisory.json()[0]["blocking"] is False
    second = client.post(entity_api, json=payload)
    assert second.is_success
    assert second.json()["id"] != first["id"]
    assert client.put(
        f"{entity_api}/{second.json()['id']}", json={"data": payload["data"]}
    ).is_success


@pytest.mark.parametrize(
    "old,new,blocked,advisory",
    [
        ({"registration_state": "CA"}, {"registration_state": "NY"}, False, False),
        ({"registration_state": "CA"}, {}, False, True),
        ({}, {}, False, True),
        ({"registration_state": "CA"}, {"registration_state": " ca "}, True, True),
        (
            {"registration_state": "CA", "vin": "one"},
            {"registration_state": "CA", "vin": "two"},
            False,
            True,
        ),
        ({"vin": "one"}, {"vin": " ONE "}, True, True),
    ],
)
def test_plate_policy(client, entity_api, old, new, blocked, advisory):
    first = client.post(
        entity_api,
        json={"entity_type": "vehicle", "data": {"license_plate": "ABC", **old}},
    )
    assert first.is_success
    payload = {"entity_type": "vehicle", "data": {"license_plate": " abc ", **new}}
    result = client.post(f"{entity_api}/duplicate-advisories", json=payload)
    assert result.is_success
    assert bool(result.json()) == advisory
    if advisory:
        assert result.json()[0]["blocking"] == blocked
    other = client.post(
        entity_api, json={"entity_type": "vehicle", "data": {"vin": "unrelated"}}
    ).json()
    result = client.put(f"{entity_api}/{other['id']}", json={"data": payload["data"]})
    assert result.status_code == (400 if blocked else 200)
    assert client.delete(f"{entity_api}/{other['id']}").is_success
    result = client.post(entity_api, json=payload)
    assert result.status_code == (400 if blocked else 201)


@pytest.mark.parametrize(
    "kind,data",
    [
        ("person", {"email": "lead@example.com"}),
        ("person", {"phone": "+1 (555) 123-4567"}),
        ("person", {"employer": "Acme"}),
        ("person", {"social_media": {"linkedin": "https://example.com/profile"}}),
        ("person", {"usernames": ["https://example.com/profile"]}),
        ("vehicle", {"vin": "known-vin"}),
        ("vehicle", {"license_plate": "ABC", "registration_state": " ca "}),
    ],
)
def test_incomplete_lifecycle(client, entity_api, kind, data):
    created = client.post(entity_api, json={"entity_type": kind, "data": data})
    assert created.is_success, created.text
    entity = created.json()
    saved = entity["data"]
    if kind == "vehicle" and "registration_state" in data:
        assert saved["registration_state"] == "CA"
    advisory = client.post(
        f"{entity_api}/duplicate-advisories?exclude_id={entity['id']}",
        json={"entity_type": kind, "data": saved},
    )
    assert advisory.json() == []
    saved["notes"] = "Updated"
    updated = client.put(f"{entity_api}/{entity['id']}", json={"data": saved})
    assert updated.is_success, updated.text
    assert (
        client.get(f"{entity_api}/{entity['id']}").json()["data"]
        == updated.json()["data"]
    )
    assert (
        client.get(f"{entity_api}/export?format=json").json()[0]["data"]
        == updated.json()["data"]
    )
    assert (
        client.put(
            f"{entity_api}/{entity['id']}", json={"data": {"notes": "blank"}}
        ).status_code
        == 422
    )


@pytest.mark.parametrize("name", ["A_C", "A%C"])
@pytest.mark.parametrize("kind,field", [("person", "first_name"), ("company", "name")])
def test_literal_names(client, entity_api, name, kind, field):
    assert client.post(
        entity_api, json={"entity_type": kind, "data": {field: "ABC"}}
    ).is_success
    payload = {"entity_type": kind, "data": {field: name}}
    assert client.post(f"{entity_api}/duplicate-advisories", json=payload).json() == []
    assert client.post(entity_api, json=payload).is_success
    payload["data"][field] = f" {name.lower()} "
    assert client.post(f"{entity_api}/duplicate-advisories", json=payload).json()
    assert client.post(entity_api, json=payload).status_code == (
        201 if kind == "person" else 400
    )


def test_advisory_access_and_case_scope(
    client, entity_api, session, test_admin, test_user
):
    other = Case(case_number="OTHER")
    session.add(other)
    session.commit()
    payload = {"entity_type": "person", "data": {"first_name": "Restricted name"}}
    hidden = client.post(
        f"{settings.API_V1_STR}/cases/{other.id}/entities", json=payload
    ).json()
    assert client.post(f"{entity_api}/duplicate-advisories", json=payload).json() == []
    assert (
        client.post(
            f"{entity_api}/duplicate-advisories?exclude_id={hidden['id']}", json=payload
        ).status_code
        == 404
    )
    client.post(entity_api, json=payload)
    app.dependency_overrides[get_current_user] = lambda: test_user
    denied = client.post(f"{entity_api}/duplicate-advisories", json=payload)
    assert denied.status_code in (403, 404)
    assert "Restricted name" not in denied.text


@pytest.mark.asyncio
@pytest.mark.parametrize("literal", ["A_C", "A%C"])
async def test_plugin_enrichment_uses_literal_and_historical_identity(
    client, entity_api, session, test_admin, literal
):
    from app.database.models import Entity
    from app.plugins.plugin_context import ServiceEntitySink
    from app.plugins.plugin_types import DomainSubdomainsWrite, IpAddressWrite

    case_id = int(entity_api.split("/")[-2])
    raw = Entity(
        created_by_id=test_admin.id,
        case_id=case_id,
        entity_type="domain",
        data={"domain": " Example.COM. "},
    )
    wrong = Entity(
        created_by_id=test_admin.id,
        case_id=case_id,
        entity_type="ip_address",
        data={"ip_address": "ABC", "description": "untouched"},
    )
    exact = Entity(
        created_by_id=test_admin.id,
        case_id=case_id,
        entity_type="ip_address",
        data={"ip_address": literal, "description": "original"},
    )
    session.add_all([raw, wrong, exact])
    session.commit()
    await ServiceEntitySink(session).write(
        IpAddressWrite(address=f" {literal} ", description="enriched"), case_id, test_admin
    )
    await ServiceEntitySink(session).write(
        DomainSubdomainsWrite(domain="example.com", subdomains=[]), case_id, test_admin
    )
    entities = client.get(entity_api).json()
    assert len(entities) == 3
    saved = {item["id"]: item["data"] for item in entities}
    assert saved[wrong.id]["description"] == "untouched"
    assert "enriched" in saved[exact.id]["description"]
    assert saved[raw.id]["domain"] == "example.com"
