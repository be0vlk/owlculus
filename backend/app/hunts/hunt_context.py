"""
Hunt context for managing data flow between hunt steps
"""

from typing import Any

from .base_hunt import HuntStepDefinition
from .step_input_resolver import ABSENT, resolve_step_input


class HuntContext:
    """Manages data flow and state between hunt steps"""

    def __init__(self, initial_parameters: dict[str, Any]):
        self.initial_parameters = initial_parameters
        self.step_outputs: dict[str, Any] = {}
        self.failed_steps: list[str] = []
        self.skipped_steps: list[str] = []

    def set_step_output(self, step_id: str, output: Any):
        """Store output from a completed step"""
        self.step_outputs[step_id] = output

    def mark_step_failed(self, step_id: str):
        """Mark a step as failed"""
        if step_id not in self.failed_steps:
            self.failed_steps.append(step_id)

    def mark_step_skipped(self, step_id: str):
        """Mark a step as skipped"""
        if step_id not in self.skipped_steps:
            self.skipped_steps.append(step_id)

    def resolve_parameters(self, step_def: HuntStepDefinition) -> dict[str, Any]:
        """
        Resolve parameters for a step using mapping rules

        Mapping syntax:
        - "initial.param_key" - Get from initial parameters
        - "step_id.output_key" - Get from step output
        - "step_id.output.nested.key" - Get nested value from step output
        """
        resolved = step_def.static_parameters.copy()

        for param_name, mapping_expr in step_def.parameter_mapping.items():
            value = resolve_step_input(
                mapping_expr, self.initial_parameters, self.step_outputs
            )
            if value is not ABSENT:
                resolved[param_name] = value

        return resolved

    def to_dict(self) -> dict:
        """Convert context to dictionary for storage"""
        return {
            "initial_parameters": self.initial_parameters,
            "step_outputs": self.step_outputs,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
        }
