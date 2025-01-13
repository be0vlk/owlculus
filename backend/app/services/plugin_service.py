"""
Service for managing and executing plugins
"""

import os
import importlib
import inspect
from typing import Dict, Type, AsyncGenerator, Any
from ..plugins.base_plugin import BasePlugin
from app.core.dependencies import no_analyst
from ..database.models import User
from sqlmodel import Session


class PluginService:
    def __init__(self, db: Session):
        self._plugins: Dict[str, Type[BasePlugin]] = {}
        self.db = db
        self._load_plugins()

    def _load_plugins(self) -> None:
        """Automatically load all plugins from the plugins directory"""
        plugins_dir = os.path.dirname(os.path.dirname(__file__)) + "/plugins"
        for filename in os.listdir(plugins_dir):
            if filename.endswith("_plugin.py") and filename != "base_plugin.py":
                module_name = filename[:-3]  # Remove .py
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
                        plugin = obj()
                        self._plugins[plugin.name] = obj

    def get_plugin(self, name: str) -> BasePlugin:
        """Get a plugin instance by name"""
        if name not in self._plugins:
            raise ValueError(f"Plugin {name} not found")
        return self._plugins[name]()

    @no_analyst()
    async def list_plugins(self, *, current_user: User) -> Dict[str, Any]:
        """List all registered plugins and their metadata"""
        return {name: plugin().get_metadata() for name, plugin in self._plugins.items()}

    @no_analyst()
    async def execute_plugin(
        self, name: str, params: Dict[str, Any] = None, *, current_user: User
    ) -> AsyncGenerator[str, None]:
        """Execute a plugin with the given parameters"""
        plugin = self.get_plugin(name)
        plugin._current_user = current_user
        return plugin.run(params or {})


# Create a singleton instance
plugin_service = PluginService(db=Session())
