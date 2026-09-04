"""
Plugin management and execution service for Owlculus OSINT tool integration.

This module handles all plugin-related operations including dynamic plugin loading,
execution management, and evidence collection integration. Provides extensible
OSINT tool integration with automatic plugin discovery, parameter validation,
and real-time streaming execution for investigation workflows.
"""

import importlib
import inspect
import json
import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlmodel import Session

from app.core.exceptions import ResourceNotFoundException, ValidationException

from ..database.models import User
from ..plugins.base_plugin import BasePlugin
from .api_key_vault import Provider
from .case_access import CaseAccess


class PluginService:
    def __init__(self, db: Session):
        self._plugins: dict[str, type[BasePlugin]] = {}
        self._parameter_catalogue: dict[str, set[str]] = {}
        self.db = db
        self.case_access = CaseAccess(db)
        self._load_plugins()

    def _load_plugins(self) -> None:
        plugins_dir = os.path.dirname(os.path.dirname(__file__)) + "/plugins"
        for filename in os.listdir(plugins_dir):
            if filename.endswith("_plugin.py") and filename != "base_plugin.py":
                module_name = filename[:-3]
                module = importlib.import_module(
                    f"..plugins.{module_name}", package=__package__
                )

                for _, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, BasePlugin)
                        and obj != BasePlugin
                    ):
                        plugin = obj(db_session=self.db)
                        if any(
                            not isinstance(provider, Provider)
                            for provider in plugin.api_key_requirements
                        ):
                            raise ValidationException(
                                f"{obj.__name__} declares unknown API key provider"
                            )
                        self._plugins[obj.__name__] = obj
                        self._parameter_catalogue[obj.__name__] = set(plugin.parameters)

    def get_plugin(self, name: str) -> BasePlugin:
        if name not in self._plugins:
            raise ResourceNotFoundException(f"Plugin {name} not found")
        return self._plugins[name](db_session=self.db)

    def parameter_catalogue(self) -> dict[str, set[str]]:
        """Return the declared input names for every discovered plugin."""
        return {
            name: parameters.copy()
            for name, parameters in self._parameter_catalogue.items()
        }

    async def list_plugins(self, *, current_user: User) -> dict[str, Any]:
        self.case_access.require_non_analyst(current_user)
        plugins_metadata = {}
        for name, plugin_class in self._plugins.items():
            plugin_instance = plugin_class(db_session=self.db)
            metadata = plugin_instance.get_metadata()
            plugins_metadata[name] = metadata
        return plugins_metadata

    async def execute_plugin(
        self, name: str, params: dict[str, Any] | None = None, *, current_user: User
    ) -> AsyncGenerator[dict[str, Any], None]:
        self.case_access.require_non_analyst(current_user)
        plugin = self.get_plugin(name)
        plugin._current_user = current_user
        return plugin.execute_with_evidence_collection(params or {})

    async def stream_plugin_execution(
        self,
        name: str,
        params: dict[str, Any] | None = None,
        *,
        current_user: User,
    ) -> AsyncGenerator[str, None]:
        """Execute a plugin while preserving the NDJSON streaming contract."""
        self.case_access.require_non_analyst(current_user)

        async def stream() -> AsyncGenerator[str, None]:
            try:
                result = await self.execute_plugin(
                    name, params, current_user=current_user
                )
                async for line in result:
                    yield json.dumps(line) + "\n"
            except ResourceNotFoundException as error:
                yield (
                    json.dumps({"type": "error", "data": {"message": str(error)}})
                    + "\n"
                )
            except Exception as error:
                yield json.dumps(
                    {
                        "type": "error",
                        "data": {"message": f"Plugin execution error: {str(error)}"},
                    }
                ) + "\n"

        return stream()
