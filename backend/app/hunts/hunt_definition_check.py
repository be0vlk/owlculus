"""Startup validation for hunt definitions and their plugin inputs."""

from collections.abc import Collection, Mapping
from typing import NoReturn

from pydantic import ValidationError

from .base_hunt import BaseHunt, HuntStepDefinition


class HuntDefinitionError(ValueError):
    """Raised when a hunt cannot be registered safely."""


class HuntDefinitionCheck:
    """Check a hunt against the currently shipped plugin catalogue."""

    def __init__(self, plugin_parameters: Mapping[str, Collection[str]]):
        self._plugin_parameters = plugin_parameters

    def check(self, hunt: BaseHunt) -> None:
        earlier_steps: set[str] = set()
        try:
            steps = hunt.get_steps()
        except ValidationError as error:
            raise HuntDefinitionError(f"Hunt {hunt.name}: {error}") from error

        for step in steps:
            self._check_step(hunt, step, earlier_steps)
            earlier_steps.add(step.step_id)

    def _check_step(
        self,
        hunt: BaseHunt,
        step: HuntStepDefinition,
        earlier_steps: set[str],
    ) -> None:
        declared_parameters = self._plugin_parameters.get(step.plugin_name)
        if declared_parameters is None:
            self._fail(
                hunt,
                step,
                f"plugin '{step.plugin_name}' is not registered",
            )

        for parameter in (*step.parameter_mapping, *step.static_parameters):
            if parameter not in declared_parameters:
                self._fail(
                    hunt,
                    step,
                    f"parameter '{parameter}' is not declared by {step.plugin_name}",
                )

        for dependency in step.depends_on:
            if dependency not in earlier_steps:
                self._fail(
                    hunt,
                    step,
                    f"dependency '{dependency}' does not name an earlier step",
                )

        for expression in step.parameter_mapping.values():
            if expression.source == "initial":
                initial_parameter = expression.path[0]
                if initial_parameter not in hunt.initial_parameters:
                    self._fail(
                        hunt,
                        step,
                        f"input '{expression}' names an unknown initial parameter",
                    )
            elif expression.source not in earlier_steps:
                self._fail(
                    hunt,
                    step,
                    f"input '{expression}' does not name an earlier step",
                )

    @staticmethod
    def _fail(hunt: BaseHunt, step: HuntStepDefinition, problem: str) -> NoReturn:
        raise HuntDefinitionError(f"Hunt {hunt.name}, step {step.step_id}: {problem}")
