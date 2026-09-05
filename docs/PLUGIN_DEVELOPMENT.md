# Plugin Development Guide

An Owlculus plugin author implements one method: `run(params, ctx)`. The run
context supplies application capabilities, and the base class supplies typed event
constructors plus evidence collection. Plugins must not open database sessions or
reach into configuration and service modules themselves.

## Generate a plugin

From the repository root:

```bash
python scripts/create_plugin.py my_tool --backend-only
```

The generator creates a backend plugin and a runnable contract test by default.
The frontend automatically renders parameter metadata and result events, so custom
Vue components are optional.

## Minimal plugin

```python
from collections.abc import AsyncGenerator
from typing import Any

from .base_plugin import BasePlugin, PluginRun, ResultEvent


class MyToolPlugin(BasePlugin):
    def __init__(self):
        super().__init__(display_name="My Tool")
        self.description = "Look up a target."
        self.category = "Other"
        self.evidence_category = "Other"
        self.parameters = {
            "target": {
                "type": "string",
                "description": "Target to inspect",
                "required": True,
            }
        }

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        if "target" not in params:
            yield self.error("Target parameter is required")
            return

        yield self.status("Looking up target")
        yield self.data({"target": params["target"], "found": True})
```

Use only the event constructors `self.data(payload)`, `self.error(message)`,
`self.status(message)`, and `self.complete()`. `ResultEvent` is converted to the
existing `{ "type": ..., "data": ... }` envelope in retained execution results.
Standalone submission returns HTTP 202 with an execution reference; see
[the background execution API](background-plugin-executions.md).

## Run context

`PluginRun` contains the database session, acting user, target case ID,
`save_to_case` choice, API-key vault, evidence sink, and entity sink for exactly
one invocation. Application code builds the production adapter. Tests use
`PluginRun.for_test(...)` with a key dictionary and list sinks.

For a provider key:

```python
from app.services.api_key_vault import Provider

api_key = ctx.key(Provider.SHODAN)
if not api_key:
    yield ctx.missing_key(Provider.SHODAN)
    return
```

This keeps missing-key guidance consistent. Never log a key or include one in an
event or evidence payload.

## Evidence formatting

The base collects only data payloads. Override `format_evidence` when plain JSON is
not suitable; its first argument is the typed list of inner payloads, not event
envelopes:

```python
def format_evidence(
    self, payloads: list[dict[str, Any]], params: dict[str, Any]
) -> str:
    return "\n".join(item["finding"] for item in payloads)
```

The base adds the `save_to_case` metadata parameter automatically. Do not define a
plugin instance attribute for it.

## Subprocess plugins

Ordinary API and library plugins inherit only `BasePlugin`. A command-line plugin
also opts into `SubprocessPluginMixin` and implements `parse_output`; only that
mixin allocates a short-lived thread pool.

## Categories

UI categories are `Person`, `Network`, `Company`, and `Other`. Evidence categories
are `Social Media`, `Associates`, `Network Assets`, `Communications`, `Documents`,
and `Other`.

## Built-in plugins

- `CorrelationScan`
- `DnsLookup`
- `HolehePlugin`
- `PeopledatalabsPlugin`
- `ShodanPlugin`
- `SubdomainEnumPlugin`
- `VirustotalPlugin`
- `WhoisPlugin`

Plugin discovery scans `backend/app/plugins/*_plugin.py` and registers concrete
`BasePlugin` subclasses by their real class names.
