"""Discovery and persistence of registered hunt definitions."""

import importlib
import inspect
from collections.abc import Iterable, Iterator
from pathlib import Path

from sqlmodel import Session, select

from app.database.models import Hunt

from .base_hunt import BaseHunt
from .hunt_definition_check import HuntDefinitionCheck

type HuntClass = type[BaseHunt]


class HuntRegistry:
    """The startup-built catalogue of available hunt definitions."""

    def __init__(self, hunt_classes: dict[str, HuntClass]):
        self._hunt_classes = hunt_classes

    @classmethod
    def from_classes(cls, hunt_classes: Iterable[HuntClass]) -> "HuntRegistry":
        return cls({hunt_class.__name__: hunt_class for hunt_class in hunt_classes})

    @classmethod
    def from_directory(cls, directory: Path, package: str) -> "HuntRegistry":
        hunt_classes: list[HuntClass] = []
        for path in sorted(directory.glob("*_hunt.py")):
            module = importlib.import_module(f"{package}.{path.stem}")
            hunt_classes.extend(
                candidate
                for _, candidate in inspect.getmembers(module, inspect.isclass)
                if issubclass(candidate, BaseHunt)
                and candidate is not BaseHunt
                and candidate.__module__ == module.__name__
            )
        return cls.from_classes(hunt_classes)

    def names(self) -> tuple[str, ...]:
        return tuple(self._hunt_classes)

    def create(self, name: str) -> BaseHunt | None:
        hunt_class = self._hunt_classes.get(name)
        return hunt_class() if hunt_class is not None else None

    def _definitions(self) -> Iterator[tuple[str, BaseHunt]]:
        for name, hunt_class in self._hunt_classes.items():
            yield name, hunt_class()

    def check(self, definition_check: HuntDefinitionCheck) -> None:
        for _, hunt in self._definitions():
            definition_check.check(hunt)

    def sync(self, session: Session) -> None:
        """Upsert all checked definitions in one startup transaction."""
        for name, hunt in self._definitions():
            stored = session.exec(select(Hunt).where(Hunt.name == name)).first()
            if stored is None:
                stored = Hunt(
                    name=name,
                    display_name=hunt.display_name,
                    description=hunt.description,
                    category=hunt.category,
                    version=hunt.version,
                    definition_json=hunt.to_definition(),
                    is_active=True,
                )
                session.add(stored)
            else:
                stored.display_name = hunt.display_name
                stored.description = hunt.description
                stored.category = hunt.category
                stored.version = hunt.version
                stored.definition_json = hunt.to_definition()
        session.commit()


SHIPPED_HUNT_DIRECTORY = Path(__file__).parent / "definitions"
shipped_hunt_registry = HuntRegistry.from_directory(
    SHIPPED_HUNT_DIRECTORY, "app.hunts.definitions"
)
