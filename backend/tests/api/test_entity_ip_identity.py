"""Canonical IP lifecycle and Plugin enrichment through public boundaries."""

import pytest

from app.core.dependencies import get_current_user
from app.database.models import Case, Entity
from app.main import app
from app.plugins.plugin_context import ServiceEntitySink
from app.plugins.plugin_types import IpAddressWrite


@pytest.fixture
def ip_api(client, session, test_admin):
    app.dependency_overrides[get_current_user] = lambda: test_admin
    case = Case(case_number="IP-IDENTITY")
    session.add(case)
    session.commit()
    return f"/api/cases/{case.id}/entities", case.id


@pytest.mark.asyncio
async def test_historical_ip_duplicates_edits_and_enrichment(
    client, session, test_admin, ip_api
):
    url, case_id = ip_api
    old = Entity(
        case_id=case_id,
        created_by_id=test_admin.id,
        entity_type="ip_address",
        data={
            "ip_address": "2001:0DB8:0000:0000:0000:0000:0000:0001",
            "description": "original",
        },
    )
    session.add(old)
    session.commit()
    payload = {"entity_type": "ip_address", "data": {"ip_address": "2001:db8::1"}}
    advisory = client.post(f"{url}/duplicate-advisories", json=payload)
    assert advisory.is_success, advisory.text
    assert advisory.json()[0]["id"] == old.id
    assert advisory.json()[0]["blocking"] is True
    assert client.post(url, json=payload).status_code == 400
    assert (
        client.post(
            f"{url}/duplicate-advisories?exclude_id={old.id}", json=payload
        ).json()
        == []
    )
    await ServiceEntitySink(session).write(
        IpAddressWrite(address="2001:db8::1", description="enriched"),
        case_id,
        test_admin,
    )
    assert len(client.get(url).json()) == 1
    assert "enriched" in client.get(f"{url}/{old.id}").json()["data"]["description"]
    updated = client.put(
        f"{url}/{old.id}", json={"data": {**old.data, "notes": "edited"}}
    )
    assert updated.is_success, updated.text
    assert updated.json()["data"]["ip_address"] == "2001:db8::1"
    second = client.post(
        url, json={"entity_type": "ip_address", "data": {"ip_address": "2001:db8::2"}}
    ).json()
    assert (
        client.put(f"{url}/{second['id']}", json={"data": payload["data"]}).status_code
        == 400
    )


@pytest.mark.parametrize(
    "value",
    ["fe80::1%eth0", "2001:db8::/64", "IP: 2001:db8::1", "192.168.001.1", "[::1]", ""],
)
def test_unsupported_ip_rejected_on_create_and_edit(client, ip_api, value):
    url, _ = ip_api
    payload = {"entity_type": "ip_address", "data": {"ip_address": value}}
    assert client.post(url, json=payload).status_code == 422
    existing = client.post(
        url, json={"entity_type": "ip_address", "data": {"ip_address": "192.0.2.1"}}
    ).json()
    assert (
        client.put(
            f"{url}/{existing['id']}", json={"data": payload["data"]}
        ).status_code
        == 422
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "entered,alternate,canonical",
    [
        (" 192.0.2.1 ", "192.0.2.1", "192.0.2.1"),
        ("2001:0DB8:0000:0000:0000:0000:0000:0001", "2001:db8::1", "2001:db8::1"),
        ("::ffff:192.0.2.1", "0:0:0:0:0:ffff:c000:201", "::ffff:192.0.2.1"),
    ],
)
async def test_new_ip_lifecycle_and_sink_share_identity(
    client, session, test_admin, ip_api, entered, alternate, canonical
):
    url, case_id = ip_api
    payload = {"entity_type": "ip_address", "data": {"ip_address": entered}}
    created = client.post(url, json=payload)
    assert created.is_success, created.text
    record = created.json()
    assert record["data"]["ip_address"] == canonical
    payload["data"]["ip_address"] = alternate
    assert client.post(url, json=payload).status_code == 400
    await ServiceEntitySink(session).write(
        IpAddressWrite(address=alternate, description="enriched"), case_id, test_admin
    )
    saved = client.get(f"{url}/{record['id']}").json()["data"]
    assert saved["description"] == "enriched"
    for _ in range(2):
        saved["notes"] = "ordinary edit"
        updated = client.put(f"{url}/{record['id']}", json={"data": saved})
        assert updated.is_success, updated.text
        assert updated.json()["data"]["ip_address"] == canonical
    exported = client.get(f"{url}/export?format=json").json()
    assert len(exported) == 1
    assert exported[0]["data"] == updated.json()["data"]
    # A Plugin-only discovery must normalize and reuse its new Entity as well.
    for address in ("2001:0db8:0:0:0:0:0:99", "2001:db8::99"):
        await ServiceEntitySink(session).write(
            IpAddressWrite(address=address, description="discovered"),
            case_id,
            test_admin,
        )
    entities = client.get(url).json()
    assert len(entities) == 2
    assert any(item["data"]["ip_address"] == "2001:db8::99" for item in entities)
