"""The hunt progress vocabulary shared by executors and transports."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class HuntEventType(StrEnum):
    PROGRESS = "progress"
    STEP_COMPLETE = "step_complete"
    STEP_FAILED = "step_failed"
    COMPLETE = "complete"
    ERROR = "error"
    CONNECTED = "connected"


@dataclass(frozen=True)
class HuntEvent:
    event_type: HuntEventType
    execution_id: int
    step_id: str | None = None
    progress_value: float | None = None
    error_message: str | None = None
    message: str | None = None

    @classmethod
    def progress(
        cls, execution_id: int, progress: float, step_id: str | None = None
    ) -> "HuntEvent":
        return cls(HuntEventType.PROGRESS, execution_id, step_id, progress)

    @classmethod
    def step_complete(
        cls, execution_id: int, step_id: str, progress: float
    ) -> "HuntEvent":
        return cls(HuntEventType.STEP_COMPLETE, execution_id, step_id, progress)

    @classmethod
    def step_failed(
        cls, execution_id: int, step_id: str, progress: float
    ) -> "HuntEvent":
        return cls(HuntEventType.STEP_FAILED, execution_id, step_id, progress)

    @classmethod
    def complete(cls, execution_id: int) -> "HuntEvent":
        return cls(HuntEventType.COMPLETE, execution_id)

    @classmethod
    def error(cls, execution_id: int, error: str) -> "HuntEvent":
        return cls(HuntEventType.ERROR, execution_id, error_message=error)

    @classmethod
    def connected(cls, execution_id: int) -> "HuntEvent":
        return cls(
            HuntEventType.CONNECTED,
            execution_id,
            message="WebSocket connection established",
        )

    def to_wire(self) -> dict[str, str | int | float]:
        message: dict[str, str | int | float] = {
            "event_type": self.event_type.value,
            "execution_id": self.execution_id,
        }
        if self.step_id is not None:
            message["step_id"] = self.step_id
        if self.progress_value is not None:
            message["progress"] = self.progress_value
        if self.error_message is not None:
            message["error"] = self.error_message
        if self.message is not None:
            message["message"] = self.message
        return message


class HuntNotifier(Protocol):
    async def broadcast(self, event: HuntEvent) -> None:
        """Publish one hunt event."""
