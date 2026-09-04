"""Shodan plugin tests at the plugin-author contract."""

from unittest.mock import Mock

import pytest
import shodan

from app.plugins.base_plugin import PluginRun, ResultEvent
from app.plugins.shodan_plugin import ShodanPlugin
from app.services.api_key_vault import Provider


def run_context(session, user, keys, *, save=False):
    return PluginRun.for_test(
        session=session,
        user=user,
        api_keys=keys,
        evidence=[],
        entities=[],
        case_id=1,
        save_to_case=save,
    )


@pytest.mark.asyncio
async def test_missing_key_uses_context_wording(session, test_admin):
    events = [
        event
        async for event in ShodanPlugin().run(
            {"query": "192.0.2.1"}, run_context(session, test_admin, {})
        )
    ]

    assert events == [
        ResultEvent.error(
            "API key required for Shodan. Add it in Admin → Configuration → API Keys."
        )
    ]


@pytest.mark.asyncio
async def test_query_is_required_before_key_lookup(session, test_admin):
    events = [
        event
        async for event in ShodanPlugin().run({}, run_context(session, test_admin, {}))
    ]

    assert events == [ResultEvent.error("Search query parameter is required")]


@pytest.mark.asyncio
async def test_ip_query_is_auto_detected(session, test_admin, monkeypatch):
    plugin = ShodanPlugin()

    async def search(api_key, query, search_type, limit):
        assert (api_key, query, search_type, limit) == (
            "secret",
            "192.0.2.1",
            "ip",
            100,
        )
        yield plugin.data({"ip": query, "search_type": "host_lookup"})

    monkeypatch.setattr(plugin, "_search_shodan", search)
    events = [
        event
        async for event in plugin.run(
            {"query": "192.0.2.1", "limit": 500},
            run_context(session, test_admin, {Provider.SHODAN: "secret"}),
        )
    ]

    assert events == [
        ResultEvent.data({"ip": "192.0.2.1", "search_type": "host_lookup"})
    ]


@pytest.mark.asyncio
async def test_provider_exception_becomes_error_event(session, test_admin, monkeypatch):
    plugin = ShodanPlugin()

    async def search(*args):
        raise RuntimeError("provider unavailable")
        yield

    monkeypatch.setattr(plugin, "_search_shodan", search)
    events = [
        event
        async for event in plugin.run(
            {"query": "example.com"},
            run_context(session, test_admin, {Provider.SHODAN: "secret"}),
        )
    ]

    assert events == [
        ResultEvent.error("Unexpected error during Shodan search: provider unavailable")
    ]


@pytest.mark.asyncio
async def test_ip_provider_branch_shapes_host_response(
    session, test_admin, monkeypatch
):
    api = Mock()
    api.host.return_value = {
        "ip_str": "192.0.2.8",
        "hostnames": ["edge.example.com"],
        "org": "Example Org",
        "country_name": "Exampleland",
        "city": "Example City",
        "ports": [443],
        "data": [{"port": 443, "product": "nginx", "data": "TLS banner"}],
    }
    monkeypatch.setattr(shodan, "Shodan", lambda _: api)

    events = [
        event
        async for event in ShodanPlugin().run(
            {"query": "192.0.2.8"},
            run_context(session, test_admin, {Provider.SHODAN: "secret"}),
        )
    ]

    assert events[0] == ResultEvent.status("Looking up IP: 192.0.2.8")
    assert events[1].payload["search_type"] == "host_lookup"
    assert events[1].payload["services"][0]["service"] == "nginx"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "search_type", "provider_query", "result_type"),
    [
        (
            "host.example.com",
            "hostname",
            "hostname:host.example.com",
            "hostname_search",
        ),
        ("product:nginx", "general", "product:nginx", "general_search"),
    ],
)
async def test_search_provider_branches_shape_matches(
    session,
    test_admin,
    monkeypatch,
    query,
    search_type,
    provider_query,
    result_type,
):
    api = Mock()
    api.search.return_value = {
        "total": 1,
        "matches": [
            {
                "ip_str": "192.0.2.9",
                "location": {"country_name": "Exampleland"},
                "port": 443,
                "product": "nginx",
                "data": "TLS banner",
            }
        ],
    }
    monkeypatch.setattr(shodan, "Shodan", lambda _: api)

    events = [
        event
        async for event in ShodanPlugin().run(
            {"query": query, "search_type": search_type},
            run_context(session, test_admin, {Provider.SHODAN: "secret"}),
        )
    ]

    api.search.assert_called_once_with(provider_query, limit=10)
    assert events[-1].payload["search_type"] == result_type
    assert events[-1].payload["service"] == "nginx"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_message", "expected"),
    [
        ("Invalid API key", "Invalid Shodan API key"),
        ("API rate limit exceeded", "rate limit exceeded"),
        ("Query credits exhausted", "Insufficient Shodan query credits"),
    ],
)
async def test_general_search_translates_provider_errors(
    session, test_admin, monkeypatch, provider_message, expected
):
    api = Mock()
    api.search.side_effect = shodan.APIError(provider_message)
    monkeypatch.setattr(shodan, "Shodan", lambda _: api)

    events = [
        event
        async for event in ShodanPlugin().run(
            {"query": "product:nginx", "search_type": "general"},
            run_context(session, test_admin, {Provider.SHODAN: "secret"}),
        )
    ]

    assert expected in events[-1].payload["message"]


def test_entity_writes_are_derived_from_typed_payloads():
    writes = ShodanPlugin().entity_writes(
        [
            {
                "ip": "192.0.2.1",
                "search_type": "host_lookup",
                "organization": "Example Org",
                "ports": [443],
            }
        ],
        {"query": "192.0.2.1"},
    )

    assert len(writes) == 1
    assert writes[0].address == "192.0.2.1"
    assert "IP lookup" in writes[0].description
