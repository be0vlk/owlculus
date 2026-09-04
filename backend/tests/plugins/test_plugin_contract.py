"""Contract tests for the plugin author's public interface."""

from collections.abc import AsyncGenerator
from typing import Any

import pytest

from app.plugins.base_plugin import BasePlugin, PluginRun, ResultEvent
from app.services.api_key_vault import Provider
from app.services.plugin_service import PluginService


class ContractPlugin(BasePlugin):
    """Small plugin shaped exactly like generated third-party plugins."""

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        yield self.status("starting")
        yield self.data({"target": params["target"]})
        yield self.error("recoverable problem")


@pytest.mark.asyncio
async def test_plugin_runs_with_context_and_typed_events(test_admin, session):
    evidence: list[Any] = []
    entities: list[Any] = []
    ctx = PluginRun.for_test(
        session=session,
        user=test_admin,
        api_keys={Provider.SHODAN: "secret"},
        evidence=evidence,
        entities=entities,
    )

    events = [event async for event in ContractPlugin().run({"target": "x"}, ctx)]

    assert events == [
        ResultEvent.status("starting"),
        ResultEvent.data({"target": "x"}),
        ResultEvent.error("recoverable problem"),
    ]
    assert ctx.key(Provider.SHODAN) == "secret"


def test_missing_key_message_has_one_canonical_wording(test_admin, session):
    ctx = PluginRun.for_test(
        session=session,
        user=test_admin,
        api_keys={},
        evidence=[],
        entities=[],
    )

    assert ctx.missing_key(Provider.SHODAN) == ResultEvent.error(
        "API key required for Shodan. Add it in Admin → Configuration → API Keys."
    )


def test_events_keep_the_existing_wire_shape():
    assert ResultEvent.data({"value": 1}).to_wire() == {
        "type": "data",
        "data": {"value": 1},
    }
    assert ResultEvent.error("bad").to_wire() == {
        "type": "error",
        "data": {"message": "bad"},
    }
    assert ResultEvent.status("working").to_wire() == {
        "type": "status",
        "data": {"message": "working"},
    }
    assert ResultEvent.complete().to_wire() == {
        "type": "complete",
        "data": {},
    }


@pytest.mark.asyncio
async def test_test_adapters_collect_evidence_without_service_patches(
    test_admin, session
):
    evidence = []
    ctx = PluginRun.for_test(
        session=session,
        user=test_admin,
        api_keys={},
        evidence=evidence,
        entities=[],
        case_id=7,
        save_to_case=True,
    )

    events = [
        event
        async for event in ContractPlugin().execute_with_evidence_collection(
            {"target": "finding"}, ctx
        )
    ]

    assert events[1] == ResultEvent.data({"target": "finding"})
    assert len(evidence) == 1
    assert '"target": "finding"' in evidence[0].content


def test_base_plugin_has_no_run_scoped_or_subprocess_state():
    plugin = ContractPlugin()

    assert not hasattr(plugin, "_db_session")
    assert not hasattr(plugin, "_current_user")
    assert not hasattr(plugin, "save_to_case")
    assert not hasattr(plugin, "_executor")
    assert not hasattr(plugin, "parse_output")


@pytest.mark.asyncio
async def test_ndjson_boundary_pins_every_event_kind(test_admin):
    service = PluginService.__new__(PluginService)

    class Access:
        def require_non_analyst(self, user):
            return None

    async def execute_plugin(name, params, *, current_user):
        async def events():
            yield ResultEvent.data({"value": 1})
            yield ResultEvent.error("bad")
            yield ResultEvent.status("working")
            yield ResultEvent.complete()

        return events()

    service.case_access = Access()
    service.execute_plugin = execute_plugin

    stream = await service.stream_plugin_execution(
        "ContractPlugin", {}, current_user=test_admin
    )

    assert [line async for line in stream] == [
        '{"type": "data", "data": {"value": 1}}\n',
        '{"type": "error", "data": {"message": "bad"}}\n',
        '{"type": "status", "data": {"message": "working"}}\n',
        '{"type": "complete", "data": {}}\n',
    ]
