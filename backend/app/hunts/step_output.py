"""Declared persisted output shape shared by hunts and exports."""

from typing import TypedDict

from app.plugins.plugin_types import Payload


class StepOutput(TypedDict):
    results: list[Payload]
    result_count: int
    plugin: str
    errors: list[Payload]
