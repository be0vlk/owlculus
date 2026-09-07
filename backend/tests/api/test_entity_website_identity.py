"""Entity website identity across persistence, export and PluginRunner."""

import pytest
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.database.models import Case, Entity
from app.main import app
from app.plugins.base_plugin import PluginRun
from app.plugins.correlation_plugin import CorrelationScan
from app.plugins.plugin_registry import PluginRegistry
from app.plugins.plugin_runner import PluginRunner


@pytest.mark.asyncio
@pytest.mark.parametrize("historical", [False, True])
@pytest.mark.parametrize(
    "website,expected",
    [
        (
            "http://example.com/path:part?x=1#here",
            "http://example.com/path:part?x=1#here",
        ),
        ("HTTPS://EXAMPLE.COM/path", "https://example.com/path"),
        ("HtTp://Example.COM:8080/path?q=1#f", "http://example.com:8080/path?q=1#f"),
        ("example.com", "https://example.com"),
        (" example.com:8080/path?q=1#f ", "https://example.com:8080/path?q=1#f"),
        ("example.com/path", "https://example.com/path"),
        (
            "example.com/https://reference?q=http://other",
            "https://example.com/https://reference?q=http://other",
        ),
        ("example.com?q=1#f", "https://example.com?q=1#f"),
        (" https://BÜCHER.example./path ", "https://xn--bcher-kva.example/path"),
    ],
)
async def test_website_lifecycle(
    client, session, test_admin, website, expected, historical
):
    app.dependency_overrides[get_current_user] = lambda: test_admin
    source, other = Case(case_number="WEB-A"), Case(case_number="WEB-B")
    session.add_all([source, other])
    session.commit()
    base = f"{settings.API_V1_STR}/cases/{source.id}/entities"
    domain_base = f"{settings.API_V1_STR}/cases/{other.id}/entities"
    domain = "xn--bcher-kva.example" if "BÜCHER" in website else "example.com"
    assert client.post(
        domain_base, json={"entity_type": "domain", "data": {"domain": domain}}
    ).is_success
    assert client.post(
        domain_base,
        json={
            "entity_type": "company",
            "data": {"name": "Unrelated", "website": "http://unrelated.example"},
        },
    ).is_success
    data = {
        "name": "Website company",
        "website": website,
        "notes": "Initial",
        "sources": {"website": "Investigator"},
        "custom": {"keep": True},
        "address": {"city": "Paris", "custom": "keep"},
    }
    if historical:
        old = Entity(
            case_id=source.id,
            entity_type="company",
            data=data,
            created_by_id=test_admin.id,
        )
        session.add(old)
        session.commit()
        entity_id = old.id
    else:
        created = client.post(base, json={"entity_type": "company", "data": data})
        assert created.is_success, created.text
        entity_id = created.json()["id"]
    for index in range(3):
        read = client.get(f"{base}/{entity_id}")
        assert read.is_success, read.text
        saved = read.json()["data"]
        assert saved["website"] == (website if historical and index == 0 else expected)
        assert saved["custom"] == {"keep": True}
        assert saved["address"]["custom"] == "keep"
        assert saved["sources"] == data["sources"]
        exported = client.get(f"{base}/export?format=json").json()
        assert exported[0]["data"] == saved
        ctx = PluginRun.for_test(
            session=session,
            user=test_admin,
            case_id=source.id,
            api_keys={},
            evidence=[],
            entities=[],
        )
        events = [
            event
            async for event in PluginRunner(
                PluginRegistry.from_classes([CorrelationScan])
            ).run("CorrelationScan", {}, ctx)
        ]
        assert not [event for event in events if event.kind == "error"]
        groups = [
            event.payload
            for event in events
            if event.kind == "data" and event.payload.get("match_type") == "domain"
        ]
        assert len(groups) == 1
        assert groups[0]["normalized_value"] == domain
        assert len(groups[0]["matches"]) == 1
        saved["notes"] = f"Edit {index}"
        updated = client.put(f"{base}/{entity_id}", json={"data": saved})
        assert updated.is_success, updated.text
        assert updated.json()["data"]["website"] == expected
        assert updated.json()["data"]["notes"] == saved["notes"]


@pytest.mark.parametrize("historical", [False, True])
def test_domain_duplicate_identity(client, session, test_admin, historical):
    app.dependency_overrides[get_current_user] = lambda: test_admin
    case = Case(case_number="DOMAIN")
    session.add(case)
    session.commit()
    base = f"{settings.API_V1_STR}/cases/{case.id}/entities"
    raw = {"domain": " BÜCHER.example. ", "notes": "Keep"}
    if historical:
        old = Entity(
            case_id=case.id, created_by_id=test_admin.id, entity_type="domain", data=raw
        )
        session.add(old)
        session.commit()
        entity_id = old.id
    else:
        created = client.post(base, json={"entity_type": "domain", "data": raw})
        assert created.is_success, created.text
        entity_id = created.json()["id"]
    duplicate = client.post(
        base,
        json={"entity_type": "domain", "data": {"domain": "xn--bcher-kva.example"}},
    )
    assert duplicate.status_code == 400, duplicate.text
    sibling = client.post(
        base, json={"entity_type": "domain", "data": {"domain": "shop.bücher.example"}}
    )
    assert sibling.is_success
    update_duplicate = client.put(
        f"{base}/{sibling.json()['id']}", json={"data": {"domain": "bücher.example"}}
    )
    assert update_duplicate.status_code == 400
    if historical:
        assert client.get(f"{base}/{entity_id}").json()["data"] == raw
        assert client.get(f"{base}/export?format=json").json()[0]["data"] == raw
    saved = client.put(f"{base}/{entity_id}", json={"data": {**raw, "notes": "Edited"}})
    assert saved.is_success, saved.text
    assert saved.json()["data"]["domain"] == "xn--bcher-kva.example"


@pytest.mark.parametrize(
    "kind,field,value",
    [
        ("company", "website", "ftp://example.com/path"),
        ("company", "website", "mailto:ada@example.com"),
        ("company", "website", "https://http://example.com"),
        ("company", "website", "https://http//example.com"),
        ("company", "website", "example.com:wrong/path"),
        ("company", "website", "example.com:99999/path"),
        ("domain", "domain", "bad_label.example"),
        ("domain", "domain", "-bad.example"),
        ("domain", "domain", "bad-.example"),
        ("domain", "domain", "bad..example"),
        ("domain", "domain", "https://example.com"),
        ("domain", "domain", "example.com/path"),
    ],
)
def test_invalid_identifiers_rejected_on_create_and_edit(
    client, session, test_admin, kind, field, value
):
    app.dependency_overrides[get_current_user] = lambda: test_admin
    case = Case(case_number="INVALID")
    session.add(case)
    session.commit()
    base = f"{settings.API_V1_STR}/cases/{case.id}/entities"
    bad = {"name": "Company", field: value}
    response = client.post(base, json={"entity_type": kind, "data": bad})
    assert response.status_code == 422
    created = client.post(
        base,
        json={"entity_type": kind, "data": {"name": "Company", field: "example.com"}},
    )
    assert created.is_success
    updated = client.put(f"{base}/{created.json()['id']}", json={"data": bad})
    assert updated.status_code in (400, 422)
