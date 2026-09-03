"""Tests for discovering and synchronizing hunt definitions."""

from pathlib import Path

from sqlmodel import select

from app.database.models import Hunt
from app.hunts.base_hunt import BaseHunt
from app.hunts.definitions import DomainHunt, PersonHunt
from app.hunts.hunt_registry import HuntRegistry


def test_class_list_adapter_builds_a_registry():
    registry = HuntRegistry.from_classes([DomainHunt, PersonHunt])

    assert set(registry.names()) == {"DomainHunt", "PersonHunt"}


def test_directory_scan_adapter_discovers_shipped_hunts():
    definitions = Path(__file__).parents[2] / "app/hunts/definitions"

    registry = HuntRegistry.from_directory(definitions, "app.hunts.definitions")

    assert set(registry.names()) == {"DomainHunt", "PersonHunt"}


def test_registry_syncs_each_definition_to_the_database_once(session):
    class OneHunt(BaseHunt):
        def __init__(self):
            super().__init__()
            self.display_name = "One Hunt"
            self.description = "The only hunt"

        def get_steps(self):
            return []

    registry = HuntRegistry.from_classes([OneHunt])

    registry.sync(session)

    stored = session.exec(select(Hunt).where(Hunt.name == "OneHunt")).one()
    assert stored.display_name == "One Hunt"
    assert stored.definition_json["steps"] == []
