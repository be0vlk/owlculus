"""Test-only Strixy external provider; all application lifecycle code stays real."""

import json
import os
import time
from pathlib import Path
from uuid import UUID


def install():
    from app.services.strixy_service import ProviderReply, StrixyService

    def generate(self, messages, config, timeout):
        question = next(message.content for message in messages if message.role == "user")
        raw_marker, _, mode = question.partition("|")
        marker = str(UUID(raw_marker))
        root = Path(os.environ["OWLCULUS_EXECUTION_CONTROLS"])
        with (root / f"{marker}.starts").open("a") as output:
            output.write("started\n")
        sources = json.loads(messages[0].content)["sources"]
        source = next((item for item in sources if "attachment:line:1" in item["fields"]), sources[0])
        field = "attachment:line:1" if "attachment:line:1" in source["fields"] else "case_number"
        citations = [{"source_id": source["source_id"], "field": field, "excerpt": source["fields"][field]}]
        if self.on_progress:
            self.on_progress(ProviderReply(f"Partial Strixy reply {marker}", citations=citations))
        (root / f"{marker}.ready").touch()
        deadline = time.monotonic() + 90
        while not (root / f"{marker}.release").exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("Browser barrier timed out")
            time.sleep(0.1)
        source = json.loads(messages[0].content)["sources"][0]
        first = len((root / f"{marker}.starts").read_text().splitlines()) == 1
        if first and mode == "limit":
            return ProviderReply("", limit_code="output_limit")
        if first and mode == "failure":
            raise RuntimeError("Synthetic provider failure")
        return ProviderReply(
            citations=citations,
            content=f"Saved Strixy reply {marker}",
            input_tokens=12,
            output_tokens=8,
        )

    StrixyService.generate = generate
