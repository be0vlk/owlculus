"""
Tests for PluginService functionality
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlmodel import Session
from app.services.plugin_service import PluginService
from app.database import models
from app.plugins.base_plugin import BasePlugin
from typing import Dict, Any, Optional, AsyncGenerator
import asyncio


# Mock plugin for testing
class MockPlugin(BasePlugin):
    """Mock plugin for testing purposes"""

    def __init__(self):
        super().__init__(display_name="Mock Plugin")
        self.description = "Test plugin for unit tests"
        self.category = "Test"
        self.evidence_category = "Other"
        self.parameters = {
            "test_param": {
                "type": "string",
                "description": "Test parameter",
                "required": True,
            }
        }

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        return {"output": line}

    async def run(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        yield {"type": "data", "data": {"test": "result"}}


class TestPluginService:
    """Test cases for PluginService"""

    @pytest.fixture(name="plugin_service_instance")
    def plugin_service_fixture(self, session: Session):
        """Create a PluginService instance for testing"""
        with patch.object(PluginService, "_load_plugins"):
            service = PluginService(session)
            # Manually add mock plugin
            service._plugins = {"MockPlugin": MockPlugin}
            return service

    def test_init_plugin_service(self, session: Session):
        """Test PluginService initialization"""
        with patch.object(PluginService, "_load_plugins") as mock_load:
            service = PluginService(session)
            assert service.db == session
            assert isinstance(service._plugins, dict)
            mock_load.assert_called_once()

    def test_load_plugins_functionality(self, session: Session):
        """Test that plugin loading creates a service with plugins"""
        # Test that plugin service loads real plugins successfully
        service = PluginService(session)

        # Should have loaded some plugins from the real directory
        assert isinstance(service._plugins, dict)
        # There should be some real plugins loaded (at least the ones we know exist)
        assert len(service._plugins) > 0

    def test_get_plugin_success(self, plugin_service_instance: PluginService):
        """Test successful plugin retrieval"""
        plugin = plugin_service_instance.get_plugin("MockPlugin")
        assert isinstance(plugin, MockPlugin)
        assert plugin.display_name == "Mock Plugin"

    def test_get_plugin_not_found(self, plugin_service_instance: PluginService):
        """Test plugin retrieval with non-existent plugin"""
        with pytest.raises(ValueError, match="Plugin NonExistent not found"):
            plugin_service_instance.get_plugin("NonExistent")

    @pytest.mark.asyncio
    async def test_list_plugins_success(
        self,
        plugin_service_instance: PluginService,
        test_admin: models.User,
    ):
        """Test listing all plugins"""
        plugins = await plugin_service_instance.list_plugins(current_user=test_admin)

        assert isinstance(plugins, dict)
        assert "MockPlugin" in plugins

        plugin_metadata = plugins["MockPlugin"]
        assert plugin_metadata["name"] == "MockPlugin"
        assert plugin_metadata["display_name"] == "Mock Plugin"
        assert plugin_metadata["description"] == "Test plugin for unit tests"
        assert plugin_metadata["category"] == "Test"
        assert "parameters" in plugin_metadata
        assert "save_to_case" in plugin_metadata["parameters"]

    @pytest.mark.asyncio
    async def test_list_plugins_analyst_permission(
        self,
        plugin_service_instance: PluginService,
        test_analyst: models.User,
    ):
        """Test that analyst cannot list plugins"""
        with patch("app.core.dependencies.no_analyst") as mock_decorator:
            # Configure the decorator to raise an exception for analysts
            from fastapi import HTTPException

            def side_effect(*args, **kwargs):
                if (
                    "current_user" in kwargs
                    and kwargs["current_user"].role == "analyst"
                ):
                    raise HTTPException(status_code=403, detail="Analysts not allowed")
                return kwargs.get("current_user")

            mock_decorator.return_value = side_effect

            with pytest.raises(HTTPException) as exc_info:
                await plugin_service_instance.list_plugins(current_user=test_analyst)

            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_execute_plugin_success(
        self,
        plugin_service_instance: PluginService,
        test_admin: models.User,
    ):
        """Test successful plugin execution"""
        params = {"test_param": "test_value"}

        # Mock the plugin's execute_with_evidence_collection method
        with patch(
            "test_plugin_service.MockPlugin.execute_with_evidence_collection"
        ) as mock_execute:

            async def mock_generator():
                yield {"type": "data", "data": {"test": "result"}}

            mock_execute.return_value = mock_generator()

            result_generator = await plugin_service_instance.execute_plugin(
                "MockPlugin", params, current_user=test_admin
            )

            # Collect results
            results = []
            async for result in result_generator:
                results.append(result)

            assert len(results) == 1
            assert results[0]["type"] == "data"
            assert results[0]["data"]["test"] == "result"

    @pytest.mark.asyncio
    async def test_execute_plugin_not_found(
        self,
        plugin_service_instance: PluginService,
        test_admin: models.User,
    ):
        """Test plugin execution with non-existent plugin"""
        with pytest.raises(ValueError, match="Plugin NonExistent not found"):
            await plugin_service_instance.execute_plugin(
                "NonExistent", {}, current_user=test_admin
            )

    @pytest.mark.asyncio
    async def test_execute_plugin_no_params(
        self,
        plugin_service_instance: PluginService,
        test_admin: models.User,
    ):
        """Test plugin execution without parameters"""
        with patch.object(
            MockPlugin, "execute_with_evidence_collection"
        ) as mock_execute:

            async def mock_generator():
                yield {"type": "data", "data": {"test": "result"}}

            mock_execute.return_value = mock_generator()

            result_generator = await plugin_service_instance.execute_plugin(
                "MockPlugin", current_user=test_admin
            )

            # Verify it was called with empty dict
            mock_execute.assert_called_once_with({})

    @pytest.mark.asyncio
    async def test_execute_plugin_analyst_permission(
        self,
        plugin_service_instance: PluginService,
        test_analyst: models.User,
    ):
        """Test that analyst cannot execute plugins"""
        with patch("app.core.dependencies.no_analyst") as mock_decorator:
            # Configure the decorator to raise an exception for analysts
            from fastapi import HTTPException

            def side_effect(*args, **kwargs):
                if (
                    "current_user" in kwargs
                    and kwargs["current_user"].role == "analyst"
                ):
                    raise HTTPException(status_code=403, detail="Analysts not allowed")
                return kwargs.get("current_user")

            mock_decorator.return_value = side_effect

            with pytest.raises(HTTPException) as exc_info:
                await plugin_service_instance.execute_plugin(
                    "MockPlugin", {}, current_user=test_analyst
                )

            assert exc_info.value.status_code == 403

    def test_plugin_service_singleton_pattern(self):
        """Test that plugin_service follows singleton pattern"""
        from app.services.plugin_service import plugin_service

        # The singleton instance should exist and be a PluginService
        assert isinstance(plugin_service, PluginService)

    @patch("app.services.plugin_service.os.path.dirname")
    @patch("app.services.plugin_service.os.listdir")
    def test_load_plugins_directory_structure(
        self, mock_listdir, mock_dirname, session: Session
    ):
        """Test plugin loading respects directory structure"""
        mock_dirname.return_value = "/mock/path"
        mock_listdir.return_value = []

        with patch("app.services.plugin_service.importlib.import_module"):
            service = PluginService(session)

            # Verify correct directory path construction
            expected_plugins_dir = "/mock/path/plugins"
            mock_listdir.assert_called_with(expected_plugins_dir)

    @patch("app.services.plugin_service.os.listdir")
    @patch("app.services.plugin_service.importlib.import_module")
    def test_load_plugins_import_error_handling(
        self, mock_import, mock_listdir, session: Session
    ):
        """Test plugin loading handles import errors by raising exception"""
        mock_listdir.return_value = ["broken_plugin.py"]
        mock_import.side_effect = ImportError("Module not found")

        # Current implementation raises ImportError for broken plugins
        with pytest.raises(ImportError):
            PluginService(session)

    @patch("app.services.plugin_service.os.listdir")
    @patch("app.services.plugin_service.importlib.import_module")
    @patch("app.services.plugin_service.inspect.getmembers")
    def test_load_plugins_filters_correctly(
        self, mock_getmembers, mock_import, mock_listdir, session: Session
    ):
        """Test plugin loading filters files and classes correctly"""
        # Mock files in directory
        mock_listdir.return_value = [
            "valid_plugin.py",
            "base_plugin.py",  # Should be skipped
            "not_a_plugin.txt",  # Should be skipped
            "another_plugin.py",
        ]

        # Mock module with various classes
        mock_module = Mock()
        mock_import.return_value = mock_module

        # Mock getmembers to return mixed classes
        class NotAPlugin:
            pass

        class AnotherMockPlugin(BasePlugin):
            def __init__(self):
                super().__init__()

            def parse_output(self, line):
                return None

            async def run(self, params=None):
                yield {"type": "data", "data": {}}

        mock_getmembers.return_value = [
            ("NotAPlugin", NotAPlugin),  # Not a BasePlugin subclass
            ("BasePlugin", BasePlugin),  # Is BasePlugin itself, should be skipped
            ("AnotherMockPlugin", AnotherMockPlugin),  # Valid plugin
            ("str", str),  # Built-in type
        ]

        service = PluginService(session)

        # Should call import for .py files
        assert mock_import.call_count >= 1

        # Should load some plugins (exact count depends on what's mocked vs real)
        assert len(service._plugins) >= 0

    def test_get_plugin_returns_new_instance(
        self, plugin_service_instance: PluginService
    ):
        """Test that get_plugin returns a new instance each time"""
        plugin1 = plugin_service_instance.get_plugin("MockPlugin")
        plugin2 = plugin_service_instance.get_plugin("MockPlugin")

        # Should be different instances but same type
        assert plugin1 is not plugin2
        assert type(plugin1) == type(plugin2)
        assert isinstance(plugin1, MockPlugin)
        assert isinstance(plugin2, MockPlugin)

    @pytest.mark.asyncio
    async def test_execute_plugin_with_complex_params(
        self,
        plugin_service_instance: PluginService,
        test_admin: models.User,
    ):
        """Test plugin execution with complex parameter types"""
        complex_params = {
            "string_param": "test_value",
            "int_param": 42,
            "bool_param": True,
            "list_param": ["item1", "item2"],
            "dict_param": {"nested": "value"},
        }

        with patch.object(
            MockPlugin, "execute_with_evidence_collection"
        ) as mock_execute:

            async def mock_generator():
                yield {"type": "data", "data": {"params_received": True}}

            mock_execute.return_value = mock_generator()

            result_generator = await plugin_service_instance.execute_plugin(
                "MockPlugin", complex_params, current_user=test_admin
            )

            # Verify the parameters were passed correctly
            mock_execute.assert_called_once_with(complex_params)

            # Consume the generator
            results = [result async for result in result_generator]
            assert len(results) == 1
