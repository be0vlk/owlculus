"""
Base hunt class that all hunts must inherit from
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class HuntStepDefinition(BaseModel):
    """Definition of a single step in a hunt workflow"""

    step_id: str
    plugin_name: str
    display_name: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    parameter_mapping: dict[str, str] = Field(default_factory=dict)
    static_parameters: dict[str, Any] = Field(default_factory=dict)
    optional: bool = False
    save_to_case: bool = True


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

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Validate and clean initial parameters"""
        validated = {}

        for param_name, param_def in self.initial_parameters.items():
            if param_def.get("required", False) and param_name not in parameters:
                raise ValueError(f"Required parameter '{param_name}' is missing")

            if param_name in parameters:
                # TODO: Add type validation based on param_def["type"]
                validated[param_name] = parameters[param_name]
            elif "default" in param_def:
                validated[param_name] = param_def["default"]

        return validated

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

    def get_metadata(self) -> dict:
        """Get hunt metadata for listing"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "version": self.version,
            "initial_parameters": self.initial_parameters,
            "step_count": len(self.get_steps()),
        }
