"""Contract tests for the startup plugin catalogue and invocation path."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest

from app.plugins.base_plugin import BasePlugin, PluginRun, ResultEvent
from app.plugins.plugin_registry import PluginRegistry, get_shipped_plugin_registry
from app.plugins.plugin_runner import PluginRunner


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
