"""Startup-built catalogue of available investigation plugins."""

import importlib
import inspect
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.services.api_key_vault import ApiKeyVault, Provider

from .base_plugin import BasePlugin


class PluginRegistry:
    """Plugin classes and metadata discovered once at process startup."""

    def __init__(self, plugin_classes: list[type[BasePlugin]]):
        self._classes: dict[str, type[BasePlugin]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}
        for plugin_class in plugin_classes:
            plugin = plugin_class()
            if any(
                not isinstance(provider, Provider)
                for provider in plugin.api_key_requirements
            ):
                raise ValidationException(
                    f"{plugin_class.__name__} declares unknown API key provider"
                )
            self._classes[plugin_class.__name__] = plugin_class
            self._metadata[plugin_class.__name__] = plugin.get_metadata()

    @classmethod
    def from_classes(cls, plugin_classes: list[type[BasePlugin]]) -> "PluginRegistry":
        """Build a catalogue explicitly, primarily for application tests."""
        return cls(plugin_classes)

    @classmethod
    def from_directory(cls, directory: Path, package: str) -> "PluginRegistry":
        """Discover plugin classes from the production plugin package."""
        plugin_classes: list[type[BasePlugin]] = []
        for path in sorted(directory.glob("*_plugin.py")):
            if path.name in {"base_plugin.py", "subprocess_plugin.py"}:
                continue
            module = importlib.import_module(f"{package}.{path.stem}")
            plugin_classes.extend(
                candidate
                for _, candidate in inspect.getmembers(module, inspect.isclass)
                if issubclass(candidate, BasePlugin)
                and candidate is not BasePlugin
                and candidate.__module__ == module.__name__
            )
        return cls(plugin_classes)

    def create(self, name: str) -> BasePlugin:
        """Instantiate a plugin for one run."""
        plugin_class = self._classes.get(name)
        if plugin_class is None:
            raise ResourceNotFoundException(f"Plugin {name} not found")
        return plugin_class()

    def metadata(
        self, api_keys: ApiKeyVault | None = None
    ) -> dict[str, dict[str, Any]]:
        """Return cached metadata, enriched with current credential status."""
        metadata = deepcopy(self._metadata)
        if api_keys is None:
            return metadata
        for plugin_metadata in metadata.values():
            requirements = plugin_metadata["api_key_requirements"]
            plugin_metadata["api_key_status"] = {
                provider.value: api_keys.is_configured(provider)
                for provider in requirements
            }
        return metadata

    def parameter_catalogue(self) -> dict[str, set[str]]:
        """Return declared input names for startup hunt validation."""
        return {
            name: set(metadata["parameters"]) - {"save_to_case"}
            for name, metadata in self._metadata.items()
        }


@lru_cache(maxsize=1)
def get_shipped_plugin_registry() -> PluginRegistry:
    """Build the production registry once when application startup requests it."""
    return PluginRegistry.from_directory(Path(__file__).parent, "app.plugins")
