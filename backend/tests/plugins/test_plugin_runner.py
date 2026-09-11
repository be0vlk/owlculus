"""Contract tests for the startup plugin catalogue and invocation path."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from sqlmodel import select

from app.core import file_storage
from app.database import models
from app.plugins.base_plugin import BasePlugin, PluginRun, ResultEvent
from app.plugins.dnslookup_plugin import DnsLookup
from app.plugins.plugin_context import ServiceEntitySink, ServiceEvidenceSink
from app.plugins.plugin_registry import PluginRegistry, get_shipped_plugin_registry
from app.plugins.plugin_runner import PluginRunner
from app.services.api_key_vault import StaticApiKeyVault


class TrivialPlugin(BasePlugin):
    def __init__(self):
        super().__init__(display_name="Trivial plugin")
        self.description = "Returns its input."
        self.parameters = {"query": {"type": "string", "required": True}}

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        yield self.data({"query": params["query"]})


def test_class_list_registry_exposes_cached_metadata_and_parameter_catalogue():
    registry = PluginRegistry.from_classes([TrivialPlugin])

    assert registry.parameter_catalogue() == {"TrivialPlugin": {"query"}}
    assert registry.metadata()["TrivialPlugin"]["display_name"] == "Trivial plugin"
    assert isinstance(registry.create("TrivialPlugin"), TrivialPlugin)


def test_directory_registry_contains_shipped_plugins():
    assert {
        "DnsLookup",
        "HolehePlugin",
        "ShodanPlugin",
        "WhoisPlugin",
    } <= set(get_shipped_plugin_registry().parameter_catalogue())


@pytest.mark.asyncio
async def test_runner_appends_one_terminal_complete_event(session, test_user):
    registry = PluginRegistry.from_classes([TrivialPlugin])
    runner = PluginRunner(registry)
    run = PluginRun.for_test(
        session=session,
        user=test_user,
        api_keys={},
        evidence=[],
        entities=[],
    )

    events = [
        event async for event in runner.run("TrivialPlugin", {"query": "owl"}, run)
    ]

    assert events == [ResultEvent.data({"query": "owl"}), ResultEvent.complete()]


@pytest.mark.asyncio
async def test_runner_converts_plugin_exception_to_error_then_complete(
    session, test_user, throwing_plugin_class
):
    registry = PluginRegistry.from_classes([throwing_plugin_class])
    runner = PluginRunner(registry)
    run = PluginRun.for_test(
        session=session,
        user=test_user,
        api_keys={},
        evidence=[],
        entities=[],
    )

    events = [event async for event in runner.run("ThrowingPlugin", {}, run)]

    assert events == [
        ResultEvent.data({"partial": True}),
        ResultEvent.error("Plugin execution error: provider exploded"),
        ResultEvent.complete(),
    ]


@pytest.mark.asyncio
async def test_dns_lookup_saves_results_and_discovered_ips_to_case(
    session, test_admin, tmp_path, monkeypatch
):
    monkeypatch.setattr(file_storage, "UPLOAD_DIR", tmp_path / "uploads")
    addresses = ["104.20.23.154", "172.66.147.243"]
    resolve = AsyncMock(
        return_value=[Mock(to_text=Mock(return_value=address)) for address in addresses]
    )
    monkeypatch.setattr("dns.asyncresolver.Resolver.resolve", resolve)
    case = models.Case(case_number="DNS-001", title="DNS lookup regression")
    session.add(case)
    session.commit()
    session.refresh(case)
    run = PluginRun(
        session=session,
        user=test_admin,
        case_id=case.id,
        save_to_case=True,
        api_keys=StaticApiKeyVault({}),
        evidence=ServiceEvidenceSink(session),
        entities=ServiceEntitySink(session),
    )
    runner = PluginRunner(PluginRegistry.from_classes([DnsLookup]))

    events = [
        event async for event in runner.run("DnsLookup", {"domain": "example.com"}, run)
    ]

    assert [event for event in events if event.kind == "error"] == []
    assert [event.kind for event in events] == ["data", "complete"]
    assert events[0].payload["results"][0]["records"] == addresses
    evidence = session.exec(
        select(models.Evidence).where(models.Evidence.case_id == case.id)
    ).all()
    folder = next(item for item in evidence if item.is_folder)
    saved = next(item for item in evidence if not item.is_folder)
    assert folder.title == "Plugin Results"
    assert saved.parent_folder_id == folder.id
    assert saved.category == "Network Assets"
    content = (file_storage.UPLOAD_DIR / saved.content).read_bytes()
    assert "DNS Lookup Results" in content.decode("utf-8")
    assert "example.com" in content.decode("utf-8")
    assert all(address in content.decode("utf-8") for address in addresses)
    assert saved.file_hash == file_storage.calculate_file_hash(content)
    entities = session.exec(
        select(models.Entity).where(models.Entity.case_id == case.id)
    ).all()
    assert {entity.data["ip_address"] for entity in entities} == set(addresses)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event_limit,total_limit,expected_count,code",
    [(80, 1000, 1, "event_size_limit"), (1000, 90, 2, "result_size_limit")],
)
async def test_output_limit_retains_prefix_and_stops_provider(
    session, test_user, monkeypatch, event_limit, total_limit, expected_count, code
):
    monkeypatch.setenv("EXECUTION_EVENT_LIMIT_BYTES", str(event_limit))
    monkeypatch.setenv("EXECUTION_RESULT_LIMIT_BYTES", str(total_limit))

    class LimitedPlugin(BasePlugin):
        async def run(self, params, ctx):
            yield self.data({"value": "a"})
            yield self.data({"value": "b" * 60 if event_limit == 80 else "b"})
            yield self.data({"value": "c" * 60})
            raise AssertionError("Provider must stop at the first rejected event")

    run = PluginRun.for_test(
        session=session, user=test_user, api_keys={}, evidence=[], entities=[]
    )
    events = [
        event
        async for event in PluginRunner(
            PluginRegistry.from_classes([LimitedPlugin])
        ).run("LimitedPlugin", {}, run)
    ]
    assert len([event for event in events if event.kind == "data"]) == expected_count
    assert events[-2].payload["code"] == code
    assert events[-2].payload["partial"] is True
    assert events[-1] == ResultEvent.complete()
