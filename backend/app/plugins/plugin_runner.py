"""Single invocation path for all investigation plugins."""

from collections.abc import AsyncGenerator
from typing import Any

from app.core.exceptions import ResourceNotFoundException
from app.executions.correlation_visibility import (
    CORRELATION_ERROR,
    CORRELATION_PLUGIN,
    safe_error,
)

from .output_limits import OutputBudget, OutputLimitExceeded, serialized_size
from .plugin_context import PluginRun
from .plugin_registry import PluginRegistry
from .plugin_types import ResultEvent


class PluginRunner:
    """Instantiate and execute a plugin while normalizing terminal events."""

    def __init__(self, registry: PluginRegistry):
        self.registry = registry

    def event_size(self, event: ResultEvent) -> int:
        """Measure the event representation retained by this runner's adapter."""
        return serialized_size(event.to_wire())

    async def run(
        self, name: str, params: dict[str, Any], context: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        try:
            plugin = self.registry.create(name)
            budget = OutputBudget()
            async for event in plugin.execute_with_evidence_collection(params, context):
                if name == CORRELATION_PLUGIN and event.kind == "error":
                    event = ResultEvent("error", safe_error(event.payload) or {})
                budget.accept(event, size=self.event_size(event))
                if event.kind != "complete":
                    yield event
        except OutputLimitExceeded as error:
            yield ResultEvent("error", error.details)
        except ResourceNotFoundException as error:
            yield ResultEvent.error(str(error))
        except Exception as error:  # noqa: BLE001 - provider failures become events
            yield ResultEvent.error(
                CORRELATION_ERROR
                if name == CORRELATION_PLUGIN
                else f"Plugin execution error: {str(error)[:1024]}"
            )
        yield ResultEvent.complete()
