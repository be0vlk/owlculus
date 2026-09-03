"""Wire contract tests for hunt progress events."""

import pytest

from app.hunts.hunt_event import HuntEvent


@pytest.mark.parametrize(
    ("event", "wire_message"),
    [
        (
            HuntEvent.progress(7, 0.25),
            {"event_type": "progress", "progress": 0.25, "execution_id": 7},
        ),
        (
            HuntEvent.progress(7, 0.25, "dns"),
            {
                "event_type": "progress",
                "progress": 0.25,
                "execution_id": 7,
                "step_id": "dns",
            },
        ),
        (
            HuntEvent.step_complete(7, "dns", 0.5),
            {
                "event_type": "step_complete",
                "step_id": "dns",
                "progress": 0.5,
                "execution_id": 7,
            },
        ),
        (
            HuntEvent.step_failed(7, "dns", 0.0),
            {
                "event_type": "step_failed",
                "step_id": "dns",
                "progress": 0.0,
                "execution_id": 7,
            },
        ),
        (
            HuntEvent.complete(7),
            {"event_type": "complete", "execution_id": 7},
        ),
        (
            HuntEvent.error(7, "boom"),
            {"event_type": "error", "error": "boom", "execution_id": 7},
        ),
        (
            HuntEvent.connected(7),
            {
                "execution_id": 7,
                "event_type": "connected",
                "message": "WebSocket connection established",
            },
        ),
    ],
)
def test_hunt_event_wire_format(event, wire_message):
    assert event.to_wire() == wire_message
