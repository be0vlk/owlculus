"""Worker-loadable deterministic providers, only imported by the test launcher."""

import asyncio
import os
from pathlib import Path

from app.plugins.base_plugin import BasePlugin
from app.plugins.plugin_types import IpAddressWrite
from app.services.api_key_vault import Provider


class AcceptancePlugin(BasePlugin):
    def __init__(self):
        super().__init__()
        self.parameters = {
            "mode": {"type": "string", "default": "success"},
            "barrier": {"type": "string"},
            "query": {"type": "string"},
        }

    async def run(self, params, ctx):
        root = Path(os.environ["EXECUTION_TEST_DIR"])
        with (root / "provider-starts").open("a") as output:
            output.write(f"{params.get('barrier', 'none')}\n")
        if params.get("mode", "success") == "empty":
            return
        if params.get("mode", "success") == "vault":
            key = ctx.key(Provider.CUSTOM)
            if not key:
                yield ctx.missing_key(Provider.CUSTOM)
                return
            yield self.data({"configured": True, "redacted": key})
        yield self.data(
            {
                "query": params.get("query", "owl"),
                "case_id": ctx.case_id,
                "pid": os.getpid(),
            }
        )
        if params.get("barrier"):
            for _ in range(600):
                if (root / params["barrier"]).exists():
                    break
                await asyncio.sleep(0.1)
            else:
                raise RuntimeError("Test barrier timed out")
        if params.get("mode", "success") == "error":
            yield self.error("Deterministic failure")
            yield self.complete()

    def entity_writes(self, payloads, params):
        description = payloads[0].get("redacted", "Acceptance discovery")
        return [IpAddressWrite("192.0.2.10", description)]


def install():
    from app.plugins import plugin_registry

    original = plugin_registry.get_shipped_plugin_registry
    registry = original()
    # Keep shipped definitions for startup hunt validation.
    plugin_registry.get_shipped_plugin_registry = (
        lambda: plugin_registry.PluginRegistry.from_classes(
            [type(registry.create(name)) for name in registry.metadata()]
            + [AcceptancePlugin]
        )
    )


if __name__ == "__main__":
    import sys

    install()
    if sys.argv[1] == "api":
        import uvicorn

        uvicorn.run(
            "app.main:app", host="127.0.0.1", port=int(sys.argv[2]), log_level="warning"
        )
    elif sys.argv[1] in {"worker", "hunt-worker"}:
        from app.executions.celery_app import HUNT_QUEUE, QUEUE, app

        queue = HUNT_QUEUE if sys.argv[1] == "hunt-worker" else QUEUE

        app.worker_main(
            [
                "worker",
                "--pool=prefork",
                "--concurrency=2",
                "--prefetch-multiplier=1",
                f"--queues={queue}",
                "--loglevel=WARNING",
                f"--hostname={sys.argv[1]}@%h",
            ]
        )
