"""Deterministic browser provider, adapted from tests.executions.runtime.

Loaded only through the disposable runner's Python startup path. No execution
identity, definition validation, authorization, or persistence is replaced.
"""

import asyncio
import os
from pathlib import Path

from app.plugins.base_plugin import BasePlugin
from app.plugins.plugin_types import IpAddressWrite


class BrowserExecutionPlugin(BasePlugin):
    def __init__(self):
        super().__init__("Browser execution provider")
        self.parameters = {
            "marker": {"type": "string", "required": True, "label": "Marker"},
            "barrier": {"type": "string", "label": "Barrier"},
            "mode": {"type": "string", "default": "success", "label": "Mode"},
        }

    async def run(self, params, ctx):
        root = Path(os.environ["OWLCULUS_EXECUTION_CONTROLS"])
        marker = params["marker"]
        barrier = params.get("barrier")
        # Parameters are test-owned filenames, never arbitrary paths.
        for value in (marker, barrier):
            if value and (Path(value).name != value or value in {".", ".."}):
                raise ValueError("Invalid browser fixture marker")
        with (root / f"{marker}.starts").open("a") as output:
            output.write("started\n")
        yield self.data({"finding": f"Retained {marker}", "case_id": ctx.case_id})
        if barrier:
            (root / f"{barrier}.ready").touch()
            for _ in range(1800):
                if (root / f"{barrier}.release").exists():
                    break
                await asyncio.sleep(0.1)
            else:
                raise RuntimeError("Browser provider barrier timed out")
        if params.get("mode") == "error":
            yield self.error("Deterministic browser failure")

    def entity_writes(self, payloads, params):
        return [IpAddressWrite("192.0.2.10", f"Discovery {params['marker']}")]


def install():
    from app.plugins import plugin_registry

    registry = plugin_registry.get_shipped_plugin_registry()
    classes = [type(registry.create(name)) for name in registry.metadata()]
    plugin_registry.get_shipped_plugin_registry = (
        lambda: plugin_registry.PluginRegistry.from_classes(
            classes + [BrowserExecutionPlugin]
        )
    )
