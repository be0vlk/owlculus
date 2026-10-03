"""
Base hunt class that all hunts must inherit from
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .step_input_resolver import (
    HuntInputExpression,
    InputExpressionError,
    parse_input_expression,
)


class HuntStepDefinition(BaseModel):
    """Definition of a single step in a hunt workflow"""

    step_id: str
    plugin_name: str
    display_name: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    parameter_mapping: dict[str, HuntInputExpression] = Field(default_factory=dict)
    static_parameters: dict[str, Any] = Field(default_factory=dict)
    optional: bool = False
    save_to_case: bool = True

    @model_validator(mode="before")
    @classmethod
    def validate_input_expressions(cls, data: Any) -> Any:
        """Attach the step identifier to malformed-expression errors."""
        if not isinstance(data, dict):
            return data

        step_id = data.get("step_id", "<unknown>")
        for expression in data.get("parameter_mapping", {}).values():
            try:
                parse_input_expression(expression)
            except InputExpressionError as error:
                raise ValueError(f"Step {step_id}: {error}") from error
        return data


class BaseHunt(ABC):
    """Base class for all hunt definitions"""

    def __init__(self):
        self.name: str = self.__class__.__name__
        self.display_name: str = ""
        self.description: str = ""
        self.category: str = "general"
        self.version: str = "1.0.0"
        self.initial_parameters: dict[str, dict[str, Any]] = {}

    @abstractmethod
    def get_steps(self) -> list[HuntStepDefinition]:
        """Return the ordered list of steps for this hunt"""

    def to_definition(self) -> dict:
        """Convert hunt to JSON definition for storage"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "initial_parameters": self.initial_parameters,
            "steps": [step.model_dump() for step in self.get_steps()],
        }
