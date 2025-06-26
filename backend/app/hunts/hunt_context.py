"""
Hunt context for managing data flow between hunt steps
"""

from typing import Any, Dict, List, Optional

from .base_hunt import HuntStepDefinition


class HuntContext:
    """Manages data flow and state between hunt steps"""

    def __init__(self, initial_parameters: Dict[str, Any]):
        self.initial_parameters = initial_parameters
        self.step_outputs: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        self.evidence_refs: List[str] = []
        self.failed_steps: List[str] = []
        self.skipped_steps: List[str] = []

    def set_step_output(self, step_id: str, output: Any):
        """Store output from a completed step"""
        self.step_outputs[step_id] = output

    def get_step_output(self, step_id: str) -> Optional[Any]:
        """Retrieve output from a previous step"""
        return self.step_outputs.get(step_id)

    def add_evidence_ref(self, evidence_id: str):
        """Add reference to created evidence"""
        if evidence_id not in self.evidence_refs:
            self.evidence_refs.append(evidence_id)

    def mark_step_failed(self, step_id: str):
        """Mark a step as failed"""
        if step_id not in self.failed_steps:
            self.failed_steps.append(step_id)

    def mark_step_skipped(self, step_id: str):
        """Mark a step as skipped"""
        if step_id not in self.skipped_steps:
            self.skipped_steps.append(step_id)

    def resolve_parameters(self, step_def: HuntStepDefinition) -> Dict[str, Any]:
        """
        Resolve parameters for a step using mapping rules

        Mapping syntax:
        - "initial.param_key" - Get from initial parameters
        - "step_id.output_key" - Get from step output
        - "step_id.output.nested.key" - Get nested value from step output
        """
        resolved = step_def.static_parameters.copy()

        for param_name, mapping_expr in step_def.parameter_mapping.items():
            value = self._resolve_mapping(mapping_expr)
            if value is not None:
                resolved[param_name] = value

        return resolved

    def _resolve_mapping(self, mapping_expr: str) -> Optional[Any]:
        """Resolve a single mapping expression"""
        if not mapping_expr:
            return None

        parts = mapping_expr.split(".")

        if parts[0] == "initial":
            # Get from initial parameters
            return self._get_nested_value(self.initial_parameters, parts[1:])

        elif parts[0] in self.step_outputs:
            # Get from step output
            step_output = self.step_outputs[parts[0]]
            if len(parts) == 1:
                return step_output
            else:
                return self._get_nested_value(step_output, parts[1:])

        return None

    def _get_nested_value(self, data: Any, keys: List[str]) -> Optional[Any]:
        """Get nested value from dict or object"""
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif hasattr(current, key):
                current = getattr(current, key)
            else:
                return None

        return current

    def to_dict(self) -> dict:
        """Convert context to dictionary for storage"""
        return {
            "initial_parameters": self.initial_parameters,
            "step_outputs": self.step_outputs,
            "metadata": self.metadata,
            "evidence_refs": self.evidence_refs,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HuntContext":
        """Create context from stored dictionary"""
        context = cls(data.get("initial_parameters", {}))
        context.step_outputs = data.get("step_outputs", {})
        context.metadata = data.get("metadata", {})
        context.evidence_refs = data.get("evidence_refs", [])
        context.failed_steps = data.get("failed_steps", [])
        context.skipped_steps = data.get("skipped_steps", [])
        return context
