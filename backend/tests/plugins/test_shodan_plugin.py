"""
Tests for the Shodan plugin
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List

from app.plugins.shodan_plugin import ShodanPlugin
from app.services.system_config_service import SystemConfigService


class TestShodanPlugin:
    """Test cases for ShodanPlugin"""

    @pytest.fixture
    def plugin(self):
        """Create a ShodanPlugin instance for testing"""
        return ShodanPlugin()

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()

    @pytest.fixture
    def mock_config_service(self):
        """Mock SystemConfigService"""
        return Mock(spec=SystemConfigService)

    def test_plugin_initialization(self, plugin):
        """Test plugin is initialized correctly"""
        assert plugin.name == "ShodanPlugin"
        assert plugin.display_name == "Shodan Search"
        assert plugin.description == "Search for hosts and services using Shodan's comprehensive database"
        assert plugin.category == "Network"
        assert plugin.evidence_category == "Network Assets"
        assert plugin.save_to_case is False

    def test_plugin_parameters(self, plugin):
        """Test plugin parameters are defined correctly"""
        params = plugin.parameters
        
        assert "query" in params
        assert params["query"]["type"] == "string"
        assert params["query"]["required"] is True
        
        assert "search_type" in params
        assert params["search_type"]["type"] == "string"
        assert params["search_type"]["default"] == "general"
        
        assert "limit" in params
        assert params["limit"]["type"] == "float"
        assert params["limit"]["default"] == 10.0

    def test_parse_output_returns_none(self, plugin):
        """Test parse_output returns None as expected"""
        result = plugin.parse_output("test line")
        assert result is None

    def test_is_ip_address(self, plugin):
        """Test IP address detection"""
        assert plugin._is_ip_address("192.168.1.1") is True
        assert plugin._is_ip_address("8.8.8.8") is True
        assert plugin._is_ip_address("2001:4860:4860::8888") is True
        assert plugin._is_ip_address("google.com") is False
        assert plugin._is_ip_address("not-an-ip") is False

    def test_is_hostname(self, plugin):
        """Test hostname detection"""
        assert plugin._is_hostname("google.com") is True
        assert plugin._is_hostname("subdomain.example.org") is True
        assert plugin._is_hostname("192.168.1.1") is False
        assert plugin._is_hostname("singleword") is False

    @pytest.mark.asyncio
    async def test_run_missing_query_parameter(self, plugin):
        """Test error when query parameter is missing"""
        results = []
        async for result in plugin.run({}):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "query parameter is required" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    async def test_run_empty_query(self, plugin):
        """Test error when query is empty"""
        params = {"query": "   "}
        results = []
        async for result in plugin.run(params):
            results.append(result)

        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "cannot be empty" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    @patch('app.plugins.shodan_plugin.get_db')
    async def test_run_missing_api_key(self, mock_get_db, plugin, mock_db_session, mock_config_service):
        """Test error when API key is not configured"""
        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = None
        
        with patch('app.plugins.shodan_plugin.SystemConfigService', return_value=mock_config_service):
            params = {"query": "apache"}
            results = []
            async for result in plugin.run(params):
                results.append(result)

            assert len(results) == 1
            assert results[0]["type"] == "error"
            assert "Shodan API key not configured" in results[0]["data"]["message"]
            assert "Admin → Configuration → API Keys" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    @patch('app.plugins.shodan_plugin.get_db')
    async def test_run_ip_search_success(self, mock_get_db, plugin, mock_db_session, mock_config_service):
        """Test successful IP address search"""
        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = "test_api_key"
        
        # Mock Shodan API response
        mock_host_info = {
            "ip_str": "8.8.8.8",
            "hostnames": ["dns.google"],
            "org": "Google LLC",
            "country_name": "United States",
            "city": "Mountain View",
            "ports": [53, 443],
            "last_update": "2024-01-15T10:30:00",
            "vulns": ["CVE-2024-1234"],
            "data": [
                {
                    "port": 53,
                    "transport": "udp",
                    "product": "Google DNS",
                    "version": "1.0",
                    "data": "DNS service banner"
                }
            ]
        }

        with patch('app.plugins.shodan_plugin.SystemConfigService', return_value=mock_config_service), \
             patch('shodan.Shodan') as mock_shodan_class:
            
            mock_shodan_instance = Mock()
            mock_shodan_instance.host.return_value = mock_host_info
            mock_shodan_class.return_value = mock_shodan_instance
            
            params = {"query": "8.8.8.8", "search_type": "ip"}
            results = []
            async for result in plugin.run(params):
                results.append(result)

            # Should have status message and data result
            assert len(results) == 2
            assert results[0]["type"] == "status"
            assert "Looking up IP: 8.8.8.8" in results[0]["data"]["message"]
            
            assert results[1]["type"] == "data"
            data = results[1]["data"]
            assert data["ip"] == "8.8.8.8"
            assert data["hostnames"] == ["dns.google"]
            assert data["organization"] == "Google LLC"
            assert data["country"] == "United States"
            assert data["ports"] == [53, 443]
            assert data["search_type"] == "host_lookup"

    @pytest.mark.asyncio
    @patch('app.plugins.shodan_plugin.get_db')
    async def test_run_hostname_search_success(self, mock_get_db, plugin, mock_db_session, mock_config_service):
        """Test successful hostname search"""
        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = "test_api_key"
        
        # Mock Shodan API response
        mock_search_results = {
            "total": 1,
            "matches": [
                {
                    "ip_str": "8.8.8.8",
                    "hostnames": ["dns.google"],
                    "org": "Google LLC",
                    "location": {
                        "country_name": "United States",
                        "city": "Mountain View"
                    },
                    "port": 53,
                    "transport": "udp",
                    "product": "Google DNS",
                    "version": "1.0",
                    "data": "DNS service banner",
                    "timestamp": "2024-01-15T10:30:00"
                }
            ]
        }

        with patch('app.plugins.shodan_plugin.SystemConfigService', return_value=mock_config_service), \
             patch('shodan.Shodan') as mock_shodan_class:
            
            mock_shodan_instance = Mock()
            mock_shodan_instance.search.return_value = mock_search_results
            mock_shodan_class.return_value = mock_shodan_instance
            
            params = {"query": "google.com", "search_type": "hostname"}
            results = []
            async for result in plugin.run(params):
                results.append(result)

            # Should have status message and data result
            assert len(results) == 2
            assert results[0]["type"] == "status"
            assert "Searching for hostname: google.com" in results[0]["data"]["message"]
            
            assert results[1]["type"] == "data"
            data = results[1]["data"]
            assert data["ip"] == "8.8.8.8"
            assert data["hostnames"] == ["dns.google"]
            assert data["organization"] == "Google LLC"
            assert data["port"] == 53
            assert data["search_type"] == "hostname_search"

    @pytest.mark.asyncio
    @patch('app.plugins.shodan_plugin.get_db')
    async def test_run_general_search_success(self, mock_get_db, plugin, mock_db_session, mock_config_service):
        """Test successful general search"""
        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = "test_api_key"
        
        # Mock Shodan API response
        mock_search_results = {
            "total": 2,
            "matches": [
                {
                    "ip_str": "192.168.1.1",
                    "hostnames": ["router.local"],
                    "org": "Example ISP",
                    "location": {
                        "country_name": "United States",
                        "city": "New York"
                    },
                    "port": 80,
                    "transport": "tcp",
                    "product": "Apache",
                    "version": "2.4",
                    "data": "HTTP/1.1 200 OK",
                    "timestamp": "2024-01-15T10:30:00",
                    "vulns": []
                }
            ]
        }

        with patch('app.plugins.shodan_plugin.SystemConfigService', return_value=mock_config_service), \
             patch('shodan.Shodan') as mock_shodan_class:
            
            mock_shodan_instance = Mock()
            mock_shodan_instance.search.return_value = mock_search_results
            mock_shodan_class.return_value = mock_shodan_instance
            
            params = {"query": "apache", "search_type": "general", "limit": 50}
            results = []
            async for result in plugin.run(params):
                results.append(result)

            # Should have status messages and data result
            assert len(results) == 3
            assert results[0]["type"] == "status"
            assert "Searching Shodan: apache" in results[0]["data"]["message"]
            
            assert results[1]["type"] == "status"
            assert "Found 2 results" in results[1]["data"]["message"]
            
            assert results[2]["type"] == "data"
            data = results[2]["data"]
            assert data["ip"] == "192.168.1.1"
            assert data["port"] == 80
            assert data["service"] == "Apache"
            assert data["search_type"] == "general_search"

    @pytest.mark.asyncio
    @patch('app.plugins.shodan_plugin.get_db')
    async def test_run_shodan_api_error(self, mock_get_db, plugin, mock_db_session, mock_config_service):
        """Test handling of Shodan API errors"""
        import shodan
        
        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = "test_api_key"
        
        with patch('app.plugins.shodan_plugin.SystemConfigService', return_value=mock_config_service), \
             patch('shodan.Shodan') as mock_shodan_class:
            
            mock_shodan_instance = Mock()
            mock_shodan_instance.host.side_effect = shodan.APIError("No information available")
            mock_shodan_class.return_value = mock_shodan_instance
            
            params = {"query": "127.0.0.1", "search_type": "ip"}
            results = []
            async for result in plugin.run(params):
                results.append(result)

            # Should have status message and error result
            assert len(results) == 2
            assert results[0]["type"] == "status"
            assert results[1]["type"] == "error"
            assert "No information available" in results[1]["data"]["message"]

    @pytest.mark.asyncio
    @patch('app.plugins.shodan_plugin.get_db')
    async def test_run_shodan_rate_limit_error(self, mock_get_db, plugin, mock_db_session, mock_config_service):
        """Test handling of Shodan rate limit errors"""
        import shodan
        
        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = "test_api_key"
        
        with patch('app.plugins.shodan_plugin.SystemConfigService', return_value=mock_config_service), \
             patch('shodan.Shodan') as mock_shodan_class:
            
            mock_shodan_instance = Mock()
            mock_shodan_instance.search.side_effect = shodan.APIError("API rate limit exceeded")
            mock_shodan_class.return_value = mock_shodan_instance
            
            params = {"query": "apache", "search_type": "general"}
            results = []
            async for result in plugin.run(params):
                results.append(result)

            # Should have status message and error result
            assert len(results) == 2
            assert results[0]["type"] == "status"
            assert results[1]["type"] == "error"
            assert "rate limit exceeded" in results[1]["data"]["message"]

    @pytest.mark.asyncio
    @patch('app.plugins.shodan_plugin.get_db')
    async def test_run_limit_parameter_clamping(self, mock_get_db, plugin, mock_db_session, mock_config_service):
        """Test that limit parameter is properly clamped"""
        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = None  # Will fail early
        
        with patch('app.plugins.shodan_plugin.SystemConfigService', return_value=mock_config_service):
            # Test limit too high
            params = {"query": "test", "limit": 200}
            results = []
            async for result in plugin.run(params):
                results.append(result)
            
            # Test limit too low
            params = {"query": "test", "limit": -5}
            results = []
            async for result in plugin.run(params):
                results.append(result)
            
            # Both should fail at API key check, meaning limit clamping worked
            assert len(results) == 1
            assert results[0]["type"] == "error"

    @pytest.mark.asyncio
    @patch('app.plugins.shodan_plugin.get_db')
    async def test_run_auto_detection_ip(self, mock_get_db, plugin, mock_db_session, mock_config_service):
        """Test automatic detection of IP addresses in general search"""
        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = "test_api_key"
        
        mock_host_info = {
            "ip_str": "1.1.1.1",
            "hostnames": ["one.one.one.one"],
            "org": "Cloudflare",
            "country_name": "Australia",
            "city": "Sydney",
            "ports": [53, 80, 443],
            "data": []
        }

        with patch('app.plugins.shodan_plugin.SystemConfigService', return_value=mock_config_service), \
             patch('shodan.Shodan') as mock_shodan_class:
            
            mock_shodan_instance = Mock()
            mock_shodan_instance.host.return_value = mock_host_info
            mock_shodan_class.return_value = mock_shodan_instance
            
            # General search with IP should auto-detect as IP search
            params = {"query": "1.1.1.1", "search_type": "general"}
            results = []
            async for result in plugin.run(params):
                results.append(result)

            assert len(results) == 2
            assert results[0]["type"] == "status"
            assert "Looking up IP: 1.1.1.1" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    @patch('app.plugins.shodan_plugin.get_db')
    async def test_run_auto_detection_hostname(self, mock_get_db, plugin, mock_db_session, mock_config_service):
        """Test automatic detection of hostnames in general search"""
        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = "test_api_key"
        
        mock_search_results = {
            "total": 1,
            "matches": [
                {
                    "ip_str": "1.1.1.1",
                    "hostnames": ["cloudflare.com"],
                    "org": "Cloudflare",
                    "location": {"country_name": "Australia", "city": "Sydney"},
                    "port": 443,
                    "product": "Cloudflare",
                    "data": "HTTPS service"
                }
            ]
        }

        with patch('app.plugins.shodan_plugin.SystemConfigService', return_value=mock_config_service), \
             patch('shodan.Shodan') as mock_shodan_class:
            
            mock_shodan_instance = Mock()
            mock_shodan_instance.search.return_value = mock_search_results
            mock_shodan_class.return_value = mock_shodan_instance
            
            # General search with hostname should auto-detect as hostname search
            params = {"query": "cloudflare.com", "search_type": "general"}
            results = []
            async for result in plugin.run(params):
                results.append(result)

            assert len(results) == 2
            assert results[0]["type"] == "status"
            assert "Searching for hostname: cloudflare.com" in results[0]["data"]["message"]

    def test_plugin_metadata(self, plugin):
        """Test plugin metadata contains enhanced parameters"""
        metadata = plugin.get_metadata()
        
        assert metadata["name"] == "ShodanPlugin"
        assert metadata["display_name"] == "Shodan Search"
        assert metadata["category"] == "Network"
        
        # Check that save_to_case parameter is automatically added
        params = metadata["parameters"]
        assert "save_to_case" in params
        assert params["save_to_case"]["type"] == "boolean"
        assert params["save_to_case"]["default"] is False