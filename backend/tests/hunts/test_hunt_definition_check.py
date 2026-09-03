"""Registration checks for hunt definitions."""

import pytest
from pydantic import ValidationError

from app.hunts.base_hunt import BaseHunt, HuntStepDefinition
from app.hunts.definitions import DomainHunt, PersonHunt
from app.hunts.hunt_definition_check import (
    HuntDefinitionCheck,
    HuntDefinitionError,
)
from app.hunts.hunt_registry import HuntRegistry
from app.services.plugin_service import PluginService

PLUGIN_CATALOGUE = {
    "DnsLookup": {"domain", "lookup_mode", "record_types", "timeout", "nameservers"},
    "HolehePlugin": {"email", "timeout"},
    "ShodanPlugin": {"query", "search_type", "limit"},
    "SubdomainEnumPlugin": {"domain", "concurrency", "use_securitytrails"},
    "WhoisPlugin": {"domain", "timeout"},
}


class ExampleHunt(BaseHunt):
    def __init__(self, steps):
        super().__init__()
        self.name = "ExampleHunt"
        self.initial_parameters = {"target": {"type": "string", "required": True}}
        self._steps = steps

    def get_steps(self):
        return self._steps


def step(**overrides):
    values = {
        "step_id": "lookup",
        "plugin_name": "WhoisPlugin",
        "display_name": "Lookup",
        "description": "Lookup a target",
        "parameter_mapping": {"domain": "initial.target"},
    }
    values.update(overrides)
    return HuntStepDefinition(**values)


def test_rejects_a_step_whose_plugin_is_not_registered():
    hunt = ExampleHunt([step(plugin_name="PhantomPlugin")])

    with pytest.raises(
        HuntDefinitionError,
        match="ExampleHunt.*lookup.*plugin 'PhantomPlugin' is not registered",
    ):
        HuntDefinitionCheck(PLUGIN_CATALOGUE).check(hunt)


@pytest.mark.parametrize("parameter_source", ["parameter_mapping", "static_parameters"])
def test_rejects_a_step_parameter_the_plugin_does_not_declare(parameter_source):
    hunt = ExampleHunt([step(**{parameter_source: {"phantom": "initial.target"}})])

    with pytest.raises(
        HuntDefinitionError,
        match="ExampleHunt.*lookup.*parameter 'phantom'.*WhoisPlugin",
    ):
        HuntDefinitionCheck(PLUGIN_CATALOGUE).check(hunt)


def test_rejects_a_mapping_that_references_a_later_step():
    hunt = ExampleHunt(
        [
            step(parameter_mapping={"domain": "enrich.results[0]"}),
            step(step_id="enrich"),
        ]
    )

    with pytest.raises(
        HuntDefinitionError,
        match="ExampleHunt.*lookup.*enrich.*earlier step",
    ):
        HuntDefinitionCheck(PLUGIN_CATALOGUE).check(hunt)


def test_rejects_a_malformed_mapping_expression():
    with pytest.raises(
        ValidationError,
        match=r"initial\.\.target",
    ):
        step(parameter_mapping={"domain": "initial..target"})


def test_definition_check_names_hunt_and_step_for_a_malformed_expression():
    class MalformedHunt(ExampleHunt):
        def __init__(self):
            super().__init__([])
            self.name = "MalformedHunt"

        def get_steps(self):
            return [step(parameter_mapping={"domain": "initial..target"})]

    with pytest.raises(
        HuntDefinitionError,
        match=r"(?s)MalformedHunt.*lookup.*initial\.\.target",
    ):
        HuntDefinitionCheck(PLUGIN_CATALOGUE).check(MalformedHunt())


def test_registry_names_a_hunt_that_constructs_a_malformed_step_eagerly():
    class EagerMalformedHunt(ExampleHunt):
        def __init__(self):
            super().__init__([step(parameter_mapping={"domain": "initial..target"})])

    registry = HuntRegistry.from_classes([EagerMalformedHunt])

    with pytest.raises(
        HuntDefinitionError,
        match=r"(?s)EagerMalformedHunt.*lookup.*initial\.\.target",
    ):
        registry.check(HuntDefinitionCheck(PLUGIN_CATALOGUE))


def test_definition_serializes_validated_input_expressions_as_strings():
    hunt = ExampleHunt([step()])

    assert hunt.to_definition()["steps"][0]["parameter_mapping"] == {
        "domain": "initial.target"
    }


@pytest.mark.parametrize("hunt", [DomainHunt(), PersonHunt()])
def test_shipped_hunts_match_the_discovered_plugin_catalogue(hunt, session):
    catalogue = PluginService(session).parameter_catalogue()

    HuntDefinitionCheck(catalogue).check(hunt)
