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
from collections.abc import AsyncGenerator, Callable
from contextlib import AbstractContextManager, nullcontext
from typing import Any

from sqlmodel import Session

from app.core.exceptions import ResourceNotFoundException, ValidationException

from ..database.models import User
from ..plugins.base_plugin import BasePlugin, ResultEvent
from ..plugins.plugin_context import ProductionPluginRunAdapter
from .api_key_vault import ApiKeyVault, ConfigurationApiKeyVault, Provider
from .case_access import CaseAccess


class PluginService:
    def __init__(
        self,
        db: Session,
        api_keys: ApiKeyVault | None = None,
        session_factory: Callable[[], AbstractContextManager[Session]] | None = None,
    ):
        self._plugins: dict[str, type[BasePlugin]] = {}
        self._parameter_catalogue: dict[str, set[str]] = {}
        self.db = db
        self.api_keys = api_keys or ConfigurationApiKeyVault(db)
        run_vault_factory = (
            (lambda session: ConfigurationApiKeyVault(session))
            if api_keys is None or isinstance(api_keys, ConfigurationApiKeyVault)
            else (lambda _: api_keys)
        )
        self._run_adapter = ProductionPluginRunAdapter(
            session_factory or (lambda: nullcontext(self.db)),
            run_vault_factory,
        )
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
                        plugin = obj()
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
        return self._plugins[name]()

    def open_run(self, params: dict[str, Any], *, current_user: User):
        """Open the production context for one plugin invocation."""
        case_id = params.get("case_id")
        return self._run_adapter.open(
            user=current_user,
            case_id=case_id if isinstance(case_id, int) else None,
            save_to_case=params.get("save_to_case") is True,
        )

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
            plugin_instance = plugin_class()
            metadata = plugin_instance.get_metadata(self.api_keys)
            plugins_metadata[name] = metadata
        return plugins_metadata

    async def execute_plugin(
        self, name: str, params: dict[str, Any] | None = None, *, current_user: User
    ) -> AsyncGenerator[ResultEvent, None]:
        self.case_access.require_non_analyst(current_user)
        plugin = self.get_plugin(name)
        run_params = params or {}

        async def execute() -> AsyncGenerator[ResultEvent, None]:
            with self.open_run(run_params, current_user=current_user) as run:
                async for event in plugin.execute_with_evidence_collection(
                    run_params, run
                ):
                    yield event

        return execute()

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
                    wire_event = (
                        line.to_wire() if isinstance(line, ResultEvent) else line
                    )
                    yield json.dumps(wire_event) + "\n"
            except ResourceNotFoundException as error:
                yield (
                    json.dumps({"type": "error", "data": {"message": str(error)}})
                    + "\n"
                )
            except Exception as error:
                yield json.dumps(
                    {
                        "type": "error",
                        "data": {"message": f"Plugin execution error: {error!s}"},
                    }
                ) + "\n"

        return stream()
