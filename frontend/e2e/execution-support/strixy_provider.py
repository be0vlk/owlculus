"""Test-only Strixy external provider; all application lifecycle code stays real."""

import json
import os
import time
from pathlib import Path
from uuid import UUID


def install():
    from app.services.strixy_service import ProviderReply, StrixyService

    def generate(self, messages, config, timeout):
        marker = str(UUID(messages[-1].content))
        root = Path(os.environ["OWLCULUS_EXECUTION_CONTROLS"])
        with (root / f"{marker}.starts").open("a") as output:
            output.write("started\n")
        (root / f"{marker}.ready").touch()
        deadline = time.monotonic() + 90
        while not (root / f"{marker}.release").exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("Browser barrier timed out")
            time.sleep(0.1)
        source = json.loads(messages[0].content)["sources"][0]
        return ProviderReply(
            citations=[
                {
                    "source_id": source["source_id"],
                    "field": "case_number",
                    "excerpt": source["fields"]["case_number"],
                }
            ],
            content=f"Saved Strixy reply {marker}",
            input_tokens=12,
            output_tokens=8,
        )

    StrixyService.generate = generate
