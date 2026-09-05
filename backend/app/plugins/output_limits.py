"""One bounded output budget per standalone plugin or hunt step."""

import json
import os
from dataclasses import dataclass, field

from .plugin_types import ResultEvent


def serialized_size(payload: dict) -> int:
    return len(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


class OutputLimitExceeded(Exception):
    def __init__(self, code: str, limit: int):
        self.details = {
            "code": code,
            "message": f"Output exceeds the {limit}-byte {'event' if code == 'event_size_limit' else 'operation'} limit; previously retained results are partial",
            "limit_bytes": limit,
            "partial": True,
        }
        super().__init__(self.details["message"])


@dataclass
class OutputBudget:
    event_limit: int = field(
        default_factory=lambda: int(
            os.environ.get("EXECUTION_EVENT_LIMIT_BYTES", "1048576")
        )
    )
    result_limit: int = field(
        default_factory=lambda: int(
            os.environ.get("EXECUTION_RESULT_LIMIT_BYTES", "26214400")
        )
    )
    used: int = 0

    def __post_init__(self) -> None:
        if self.event_limit <= 0 or self.result_limit <= 0:
            raise ValueError("Execution output limits must be positive")

    def accept(self, event: ResultEvent) -> None:
        size = serialized_size(event.to_wire())
        if size > self.event_limit:
            raise OutputLimitExceeded("event_size_limit", self.event_limit)
        # Count all provider events: even a status-only provider cannot grow
        # retained output indefinitely. Runtime terminal diagnostics are reserved.
        if self.used + size > self.result_limit:
            raise OutputLimitExceeded("result_size_limit", self.result_limit)
        self.used += size
