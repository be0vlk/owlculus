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
    (root / "strixy-inputs.json").write_text(messages[0].content)
    (root / "strixy-visuals.json").write_text(
        json.dumps([v.model_dump() for v in messages[0].images])
    )
    source = json.loads(messages[0].content)["sources"][0]
    partial = ProviderReply(
        "Partial answer: " + messages[-1].content,
        citations=[
            {
                "source_id": source["source_id"],
                "field": "case_number",
                "excerpt": source["fields"]["case_number"],
            }
        ],
    )
    if self.on_progress:
        self.on_progress(partial)
    (root / "strixy-ready").touch()
    deadline = time.monotonic() + 30
    while not (root / "strixy-release").exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    source = json.loads(messages[0].content)["sources"][0]
    mode = (root / "strixy-mode").read_text() if (root / "strixy-mode").exists() else ""
    if mode == "failure":
        raise RuntimeError("private provider failure")
    if mode == "limit":
        return ProviderReply(
            "", input_tokens=20, output_tokens=2000, limit_code="output_limit"
        )
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

    strixy_config.get_strixy_config = lambda _db: StrixyConfig(
        runtime_seconds=int(os.environ.get("STRIXY_TEST_RUNTIME_SECONDS", "3"))
    )
