"""
Comprehensive tests for plugins API endpoints
"""

import pytest
import json
from fastapi.testclient import TestClient
from fastapi import status
from sqlmodel import Session
from unittest.mock import patch, AsyncMock
from typing import AsyncGenerator

from app.main import app
from app.database.models import User
from app.core.dependencies import get_current_active_user, get_db

client = TestClient(app)


@pytest.fixture
def test_admin(session: Session) -> User:
    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Admin",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


@pytest.fixture
def test_user(session: Session) -> User:
    user = User(
        username="testuser",
        email="testuser@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Investigator",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def test_analyst(session: Session) -> User:
    analyst = User(
        username="analyst",
        email="analyst@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Analyst",
    )
    session.add(analyst)
    session.commit()
    session.refresh(analyst)
    return analyst


def override_get_db_factory(session: Session):
    def override_get_db():
        return session
    return override_get_db


def override_get_current_user_factory(user: User):
    def override_get_current_user():
        return user
    return override_get_current_user


class TestPluginsAPI:
    """Test cases for plugins API endpoints"""

    # GET /api/plugins/ tests

    def test_list_plugins_success_admin(self, session: Session, test_admin: User):
        """Test successful plugins listing by admin"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        mock_plugins = {
            "DnsLookupPlugin": {
                "name": "DnsLookupPlugin",
                "display_name": "DNS Lookup",
                "description": "Perform DNS lookups for domains",
                "enabled": True,
                "category": "Network",
                "parameters": {
                    "domain": {
                        "type": "str",
                        "description": "Domain to lookup",
                        "required": True
                    }
                }
            },
            "HolehePlugin": {
                "name": "HolehePlugin",
                "display_name": "Holehe Email Check",
                "description": "Check email existence across platforms",
                "enabled": True,
                "category": "OSINT",
                "parameters": {
                    "email": {
                        "type": "str",
                        "description": "Email to check",
                        "required": True
                    }
                }
            }
        }
        
        try:
            with patch('app.services.plugin_service.PluginService.list_plugins') as mock_list:
                mock_list.return_value = mock_plugins
                
                response = client.get("/api/plugins/")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert len(data) == 2
                assert "DnsLookupPlugin" in data
                assert "HolehePlugin" in data
                assert data["DnsLookupPlugin"]["display_name"] == "DNS Lookup"
                assert data["HolehePlugin"]["display_name"] == "Holehe Email Check"
        finally:
            app.dependency_overrides.clear()

    def test_list_plugins_success_investigator(self, session: Session, test_user: User):
        """Test successful plugins listing by investigator"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        mock_plugins = {
            "DnsLookupPlugin": {
                "name": "DnsLookupPlugin",
                "display_name": "DNS Lookup",
                "description": "Perform DNS lookups for domains",
                "enabled": True,
                "category": "Network",
                "parameters": {}
            }
        }
        
        try:
            with patch('app.services.plugin_service.PluginService.list_plugins') as mock_list:
                mock_list.return_value = mock_plugins
                
                response = client.get("/api/plugins/")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert len(data) == 1
                assert "DnsLookupPlugin" in data
        finally:
            app.dependency_overrides.clear()

    def test_list_plugins_forbidden_analyst(self, session: Session, test_analyst: User):
        """Test plugins listing forbidden for analyst"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_analyst)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        try:
            with patch('app.services.plugin_service.PluginService.list_plugins') as mock_list:
                from fastapi import HTTPException
                mock_list.side_effect = HTTPException(status_code=403, detail="Permission denied")
                
                response = client.get("/api/plugins/")
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_list_plugins_empty_result(self, session: Session, test_admin: User):
        """Test plugins listing with no plugins available"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        try:
            with patch('app.services.plugin_service.PluginService.list_plugins') as mock_list:
                mock_list.return_value = {}
                
                response = client.get("/api/plugins/")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert len(data) == 0
        finally:
            app.dependency_overrides.clear()

    def test_list_plugins_unauthorized(self):
        """Test plugins listing without authentication"""
        response = client.get("/api/plugins/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # POST /api/plugins/{plugin_name}/execute tests

    def test_execute_plugin_success(self, session: Session, test_user: User):
        """Test successful plugin execution"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        plugin_params = {
            "domain": "example.com"
        }
        
        async def mock_execution_result():
            """Mock async generator for plugin execution"""
            yield {"type": "status", "data": {"message": "Starting DNS lookup"}}
            yield {"type": "data", "data": {"domain": "example.com", "ip": "93.184.216.34"}}
            yield {"type": "status", "data": {"message": "Lookup completed"}}
        
        try:
            with patch('app.services.plugin_service.PluginService.execute_plugin') as mock_execute:
                mock_execute.return_value = mock_execution_result()
                
                response = client.post("/api/plugins/DnsLookupPlugin/execute", json=plugin_params)
                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"
                
                # Check streaming response content
                content = response.content.decode()
                lines = [line for line in content.split('\n') if line.strip()]
                assert len(lines) >= 1
                
                # Parse first line as JSON
                first_result = json.loads(lines[0])
                assert first_result["type"] in ["status", "data"]
        finally:
            app.dependency_overrides.clear()

    def test_execute_plugin_with_no_params(self, session: Session, test_user: User):
        """Test plugin execution without parameters"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        async def mock_execution_result():
            """Mock async generator for plugin execution"""
            yield {"type": "data", "data": {"message": "Plugin executed without params"}}
        
        try:
            with patch('app.services.plugin_service.PluginService.execute_plugin') as mock_execute:
                mock_execute.return_value = mock_execution_result()
                
                response = client.post("/api/plugins/TestPlugin/execute")
                assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()

    def test_execute_plugin_not_found(self, session: Session, test_user: User):
        """Test execution of non-existent plugin"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        plugin_params = {"test": "value"}
        
        try:
            with patch('app.services.plugin_service.PluginService.execute_plugin') as mock_execute:
                mock_execute.side_effect = ValueError("Plugin 'NonExistentPlugin' not found")
                
                response = client.post("/api/plugins/NonExistentPlugin/execute", json=plugin_params)
                assert response.status_code == status.HTTP_200_OK  # Streaming response always returns 200
                
                # Check error in response content
                content = response.content.decode()
                lines = [line for line in content.split('\n') if line.strip()]
                assert len(lines) >= 1
                
                error_result = json.loads(lines[0])
                assert error_result["type"] == "error"
                assert "not found" in error_result["data"]["message"]
        finally:
            app.dependency_overrides.clear()

    def test_execute_plugin_execution_error(self, session: Session, test_user: User):
        """Test plugin execution with runtime error"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        plugin_params = {"invalid": "param"}
        
        try:
            with patch('app.services.plugin_service.PluginService.execute_plugin') as mock_execute:
                mock_execute.side_effect = Exception("Runtime error during execution")
                
                response = client.post("/api/plugins/TestPlugin/execute", json=plugin_params)
                assert response.status_code == status.HTTP_200_OK  # Streaming response always returns 200
                
                # Check error in response content
                content = response.content.decode()
                lines = [line for line in content.split('\n') if line.strip()]
                assert len(lines) >= 1
                
                error_result = json.loads(lines[0])
                assert error_result["type"] == "error"
                assert "Plugin execution error" in error_result["data"]["message"]
        finally:
            app.dependency_overrides.clear()

    def test_execute_plugin_forbidden_analyst(self, session: Session, test_analyst: User):
        """Test plugin execution forbidden for analyst"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_analyst)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        plugin_params = {"test": "value"}
        
        try:
            with patch('app.services.plugin_service.PluginService.execute_plugin') as mock_execute:
                mock_execute.side_effect = ValueError("Permission denied")
                
                response = client.post("/api/plugins/TestPlugin/execute", json=plugin_params)
                assert response.status_code == status.HTTP_200_OK  # Streaming response always returns 200
                
                # Check error in response content
                content = response.content.decode()
                lines = [line for line in content.split('\n') if line.strip()]
                assert len(lines) >= 1
                
                error_result = json.loads(lines[0])
                assert error_result["type"] == "error"
                assert "Permission denied" in error_result["data"]["message"]
        finally:
            app.dependency_overrides.clear()

    def test_execute_plugin_unauthorized(self):
        """Test plugin execution without authentication"""
        plugin_params = {"test": "value"}
        
        response = client.post("/api/plugins/TestPlugin/execute", json=plugin_params)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_execute_plugin_complex_params(self, session: Session, test_user: User):
        """Test plugin execution with complex parameters"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        complex_params = {
            "email": "test@example.com",
            "options": {
                "deep_search": True,
                "platforms": ["twitter", "instagram", "facebook"],
                "timeout": 30
            },
            "filters": ["active", "verified"]
        }
        
        async def mock_execution_result():
            """Mock async generator for plugin execution"""
            yield {"type": "status", "data": {"message": "Processing complex parameters"}}
            yield {"type": "data", "data": {"results": complex_params}}
        
        try:
            with patch('app.services.plugin_service.PluginService.execute_plugin') as mock_execute:
                mock_execute.return_value = mock_execution_result()
                
                response = client.post("/api/plugins/HolehePlugin/execute", json=complex_params)
                assert response.status_code == status.HTTP_200_OK
                
                # Verify complex params were processed
                content = response.content.decode()
                lines = [line for line in content.split('\n') if line.strip()]
                assert len(lines) >= 1
        finally:
            app.dependency_overrides.clear()

    def test_execute_plugin_streaming_multiple_results(self, session: Session, test_user: User):
        """Test plugin execution with multiple streaming results"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        async def mock_execution_result():
            """Mock async generator with multiple results"""
            yield {"type": "status", "data": {"message": "Starting scan"}}
            yield {"type": "data", "data": {"platform": "twitter", "found": True}}
            yield {"type": "data", "data": {"platform": "instagram", "found": False}}
            yield {"type": "data", "data": {"platform": "facebook", "found": True}}
            yield {"type": "status", "data": {"message": "Scan completed"}}
        
        try:
            with patch('app.services.plugin_service.PluginService.execute_plugin') as mock_execute:
                mock_execute.return_value = mock_execution_result()
                
                response = client.post("/api/plugins/HolehePlugin/execute", json={"email": "test@example.com"})
                assert response.status_code == status.HTTP_200_OK
                
                # Check multiple results in streaming response
                content = response.content.decode()
                lines = [line for line in content.split('\n') if line.strip()]
                assert len(lines) == 5  # 5 results from mock generator
                
                # Verify all results are valid JSON
                for line in lines:
                    result = json.loads(line)
                    assert result["type"] in ["status", "data"]
        finally:
            app.dependency_overrides.clear()

    # Edge cases and validation tests

    def test_execute_plugin_invalid_json_params(self, session: Session, test_user: User):
        """Test plugin execution with invalid JSON parameters"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        try:
            # Send malformed JSON
            response = client.post(
                "/api/plugins/TestPlugin/execute",
                data="invalid json",
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_execute_plugin_special_characters_in_name(self, session: Session, test_user: User):
        """Test plugin execution with special characters in plugin name"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        try:
            with patch('app.services.plugin_service.PluginService.execute_plugin') as mock_execute:
                mock_execute.side_effect = ValueError("Plugin 'TestPlugin123' not found")
                
                response = client.post("/api/plugins/TestPlugin123/execute", json={})
                assert response.status_code == status.HTTP_200_OK
                
                content = response.content.decode()
                lines = [line for line in content.split('\n') if line.strip()]
                error_result = json.loads(lines[0])
                assert error_result["type"] == "error"
        finally:
            app.dependency_overrides.clear()

    def test_execute_plugin_empty_plugin_name(self, session: Session, test_user: User):
        """Test plugin execution with empty plugin name"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        try:
            response = client.post("/api/plugins//execute", json={})
            # This should result in a 404 due to route mismatch
            assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    def test_list_plugins_service_error(self, session: Session, test_admin: User):
        """Test plugins listing when service throws unexpected error"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        try:
            with patch('app.services.plugin_service.PluginService.list_plugins') as mock_list:
                from fastapi import HTTPException
                mock_list.side_effect = HTTPException(status_code=500, detail="Unexpected service error")
                
                response = client.get("/api/plugins/")
                assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        finally:
            app.dependency_overrides.clear()

    def test_plugins_api_response_format_consistency(self, session: Session, test_admin: User):
        """Test consistent response format across plugins endpoints"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        mock_plugins = {
            "TestPlugin": {
                "name": "TestPlugin",
                "display_name": "Test Plugin",
                "description": "A test plugin",
                "enabled": True,
                "category": "Test",
                "parameters": {}
            }
        }
        
        try:
            with patch('app.services.plugin_service.PluginService.list_plugins') as mock_list:
                mock_list.return_value = mock_plugins
                
                response = client.get("/api/plugins/")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                
                # Verify response structure
                assert isinstance(data, dict)
                for plugin_name, plugin_data in data.items():
                    assert "name" in plugin_data
                    assert "display_name" in plugin_data
                    assert "description" in plugin_data
                    assert "enabled" in plugin_data
                    assert "category" in plugin_data
                    assert "parameters" in plugin_data
        finally:
            app.dependency_overrides.clear()

    def test_plugins_api_response_time(self, session: Session, test_admin: User):
        """Test API response time performance"""
        import time
        
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_admin)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        try:
            with patch('app.services.plugin_service.PluginService.list_plugins') as mock_list:
                mock_list.return_value = {}
                
                start_time = time.time()
                response = client.get("/api/plugins/")
                end_time = time.time()
                
                response_time = end_time - start_time
                
                assert response.status_code == status.HTTP_200_OK
                # Response should be reasonably fast (under 1 second for simple operations)
                assert response_time < 1.0
        finally:
            app.dependency_overrides.clear()

    def test_execute_plugin_large_parameters(self, session: Session, test_user: User):
        """Test plugin execution with large parameter payload"""
        app.dependency_overrides[get_current_active_user] = override_get_current_user_factory(test_user)
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        # Create a large parameter set
        large_params = {
            "data": ["item" + str(i) for i in range(1000)],  # 1000 items
            "config": {f"option_{i}": f"value_{i}" for i in range(100)}  # 100 config options
        }
        
        async def mock_execution_result():
            yield {"type": "data", "data": {"processed_items": len(large_params["data"])}}
        
        try:
            with patch('app.services.plugin_service.PluginService.execute_plugin') as mock_execute:
                mock_execute.return_value = mock_execution_result()
                
                response = client.post("/api/plugins/TestPlugin/execute", json=large_params)
                assert response.status_code == status.HTTP_200_OK
                
                content = response.content.decode()
                lines = [line for line in content.split('\n') if line.strip()]
                assert len(lines) >= 1
                
                result = json.loads(lines[0])
                assert result["type"] == "data"
        finally:
            app.dependency_overrides.clear()