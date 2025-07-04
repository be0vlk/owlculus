"""
Service for managing and executing plugins
"""

import importlib
import inspect
import os
from typing import Any, AsyncGenerator, Dict, Type

from app.core.exceptions import ResourceNotFoundException
from sqlmodel import Session

from ..database.models import User
from ..plugins.base_plugin import BasePlugin


class PluginService:
    def __init__(self, db: Session):
        self._plugins: Dict[str, Type[BasePlugin]] = {}
        self.db = db
        self._load_plugins()

    def _load_plugins(self) -> None:
        plugins_dir = os.path.dirname(os.path.dirname(__file__)) + "/plugins"
        for filename in os.listdir(plugins_dir):
            if filename.endswith("_plugin.py") and filename != "base_plugin.py":
                module_name = filename[:-3]
                module = importlib.import_module(
                    f"..plugins.{module_name}", package=__package__
                )

                # Find plugin classes in the module
                for _, obj in inspect.getmembers(module):
                    if (
                        inspect.isclass(obj)
                        and issubclass(obj, BasePlugin)
                        and obj != BasePlugin
                    ):
                        self._plugins[obj.__name__] = obj

    def get_plugin(self, name: str) -> BasePlugin:
        if name not in self._plugins:
            raise ResourceNotFoundException(f"Plugin {name} not found")
        return self._plugins[name](db_session=self.db)

    async def list_plugins(self, *, current_user: User) -> Dict[str, Any]:
        plugins_metadata = {}
        for name, plugin_class in self._plugins.items():
            plugin_instance = plugin_class(db_session=self.db)
            metadata = plugin_instance.get_metadata()
            plugins_metadata[name] = metadata
        return plugins_metadata

    async def execute_plugin(
        self, name: str, params: Dict[str, Any] = None, *, current_user: User
    ) -> AsyncGenerator[str, None]:
        plugin = self.get_plugin(name)
        plugin._current_user = current_user
        return plugin.execute_with_evidence_collection(params or {})
