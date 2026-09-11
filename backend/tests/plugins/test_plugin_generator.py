"""Contract test for the plugin generator's backend output."""

import importlib.util
import sys
from pathlib import Path

import pytest

from app.plugins.base_plugin import PluginRun, ResultEvent


def load_generator():
    path = Path(__file__).parents[3] / "scripts" / "create_plugin.py"
    spec = importlib.util.spec_from_file_location("create_plugin", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_generated_plugin_loads_and_runs(tmp_path, session, test_admin):
    generator = load_generator()
    source = generator.generate_backend_plugin(
        {
            "name": "generated_contract",
            "class_name": "GeneratedContract",
            "display_name": "Generated Contract",
            "description": "Generated plugin contract test",
            "category": "Other",
            "evidence_category": "Other",
        }
    )
    path = tmp_path / "generated_contract_plugin.py"
    path.write_text(source)
    module_name = "app.plugins.generated_contract_plugin"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        plugin = module.GeneratedContractPlugin()
        ctx = PluginRun.for_test(
            session=session,
            user=test_admin,
            api_keys={},
            evidence=[],
            entities=[],
        )

        events = [event async for event in plugin.run({"target": "example"}, ctx)]
    finally:
        sys.modules.pop(module_name, None)

    assert events == [
        ResultEvent.data(
            {
                "target": "example",
                "status": "analyzed",
                "findings": [{"type": "info", "description": "Example finding"}],
                "timestamp": events[0].payload["timestamp"],
            }
        )
    ]
