"""Single invocation path for all investigation plugins."""

from collections.abc import AsyncGenerator
from typing import Any

from app.core.exceptions import ResourceNotFoundException

from .plugin_context import PluginRun
from .plugin_registry import PluginRegistry
from .plugin_types import ResultEvent


class PluginRunner:
    """Instantiate and execute a plugin while normalizing terminal events."""

    def __init__(self, registry: PluginRegistry):
        self.registry = registry

    async def run(
        self, name: str, params: dict[str, Any], context: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        try:
            plugin = self.registry.create(name)
            async for event in plugin.execute_with_evidence_collection(params, context):
                if event.kind != "complete":
                    yield event
        except ResourceNotFoundException as error:
            yield ResultEvent.error(str(error))
        except Exception as error:  # noqa: BLE001 - provider failures become events
            yield ResultEvent.error(f"Plugin execution error: {error!s}")
        yield ResultEvent.complete()
