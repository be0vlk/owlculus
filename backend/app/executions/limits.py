"""Execution lifetimes include the reserved process cleanup budget."""

import os


def seconds(name: str, default: int) -> int:
    value = int(os.environ.get(name, default))
    if value <= 5:
        raise ValueError(f"{name} must exceed the five-second cleanup budget")
    return value


CLEANUP_SECONDS = 5
PLUGIN_SECONDS = seconds("PLUGIN_EXECUTION_SECONDS", 900)
STEP_SECONDS = seconds("HUNT_STEP_SECONDS", 900)
HUNT_SECONDS = seconds("HUNT_EXECUTION_SECONDS", 7200)
VISIBILITY_SECONDS = max(10800, HUNT_SECONDS + 60, PLUGIN_SECONDS + 60)
