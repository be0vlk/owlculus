"""Deterministic external model substitute, loaded only by acceptance workers."""

import json
import os
import time
from pathlib import Path

from app.core.strixy_config import StrixyConfig
from app.services.strixy_service import ProviderReply, StrixyService


def generate(self, messages, config, timeout):
    root = Path(os.environ["EXECUTION_TEST_DIR"])
    with (root / "strixy-starts").open("a") as output:
        output.write("started\n")
    (root / "strixy-ready").touch()
    deadline = time.monotonic() + 30
    while not (root / "strixy-release").exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    source = json.loads(messages[0].content)["sources"][0]
    return ProviderReply(
        citations=[
            {
                "source_id": source["source_id"],
                "field": "case_number",
                "excerpt": source["fields"]["case_number"],
            }
        ],
        content=f"Saved answer: {messages[-1].content}",
        input_tokens=20,
        output_tokens=10,
    )


def install():
    StrixyService.generate = generate
    from app.core import strixy_config

    strixy_config.get_strixy_config = lambda: StrixyConfig(runtime_seconds=3)
