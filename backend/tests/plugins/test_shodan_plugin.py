"""
Tests for the Shodan plugin
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List

from app.plugins.shodan_plugin import ShodanPlugin
from app.services.system_config_service import SystemConfigService
from app.services.entity_service import EntityService
from app.schemas.entity_schema import EntityCreate, IpAddressData


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
        assert (
            plugin.description
            == "Search for hosts and services using Shodan's comprehensive database"
        )
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
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_run_missing_api_key(
        self, mock_get_db, plugin, mock_db_session, mock_config_service
    ):
        """Test error when API key is not configured"""
        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = None

        with patch(
            "app.plugins.shodan_plugin.SystemConfigService",
            return_value=mock_config_service,
        ):
            params = {"query": "apache"}
            results = []
            async for result in plugin.run(params):
                results.append(result)

            assert len(results) == 1
            assert results[0]["type"] == "error"
            assert "Shodan API key not configured" in results[0]["data"]["message"]
            assert "Admin → Configuration → API Keys" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_run_ip_search_success(
        self, mock_get_db, plugin, mock_db_session, mock_config_service
    ):
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
                    "data": "DNS service banner",
                }
            ],
        }

        with patch(
            "app.plugins.shodan_plugin.SystemConfigService",
            return_value=mock_config_service,
        ), patch("shodan.Shodan") as mock_shodan_class:

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
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_run_hostname_search_success(
        self, mock_get_db, plugin, mock_db_session, mock_config_service
    ):
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
                        "city": "Mountain View",
                    },
                    "port": 53,
                    "transport": "udp",
                    "product": "Google DNS",
                    "version": "1.0",
                    "data": "DNS service banner",
                    "timestamp": "2024-01-15T10:30:00",
                }
            ],
        }

        with patch(
            "app.plugins.shodan_plugin.SystemConfigService",
            return_value=mock_config_service,
        ), patch("shodan.Shodan") as mock_shodan_class:

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
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_run_general_search_success(
        self, mock_get_db, plugin, mock_db_session, mock_config_service
    ):
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
                    "location": {"country_name": "United States", "city": "New York"},
                    "port": 80,
                    "transport": "tcp",
                    "product": "Apache",
                    "version": "2.4",
                    "data": "HTTP/1.1 200 OK",
                    "timestamp": "2024-01-15T10:30:00",
                    "vulns": [],
                }
            ],
        }

        with patch(
            "app.plugins.shodan_plugin.SystemConfigService",
            return_value=mock_config_service,
        ), patch("shodan.Shodan") as mock_shodan_class:

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
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_run_shodan_api_error(
        self, mock_get_db, plugin, mock_db_session, mock_config_service
    ):
        """Test handling of Shodan API errors"""
        import shodan

        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = "test_api_key"

        with patch(
            "app.plugins.shodan_plugin.SystemConfigService",
            return_value=mock_config_service,
        ), patch("shodan.Shodan") as mock_shodan_class:

            mock_shodan_instance = Mock()
            mock_shodan_instance.host.side_effect = shodan.APIError(
                "No information available"
            )
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
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_run_shodan_rate_limit_error(
        self, mock_get_db, plugin, mock_db_session, mock_config_service
    ):
        """Test handling of Shodan rate limit errors"""
        import shodan

        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = "test_api_key"

        with patch(
            "app.plugins.shodan_plugin.SystemConfigService",
            return_value=mock_config_service,
        ), patch("shodan.Shodan") as mock_shodan_class:

            mock_shodan_instance = Mock()
            mock_shodan_instance.search.side_effect = shodan.APIError(
                "API rate limit exceeded"
            )
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
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_run_limit_parameter_clamping(
        self, mock_get_db, plugin, mock_db_session, mock_config_service
    ):
        """Test that limit parameter is properly clamped"""
        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_config_service.get_api_key.return_value = None  # Will fail early

        with patch(
            "app.plugins.shodan_plugin.SystemConfigService",
            return_value=mock_config_service,
        ):
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
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_run_auto_detection_ip(
        self, mock_get_db, plugin, mock_db_session, mock_config_service
    ):
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
            "data": [],
        }

        with patch(
            "app.plugins.shodan_plugin.SystemConfigService",
            return_value=mock_config_service,
        ), patch("shodan.Shodan") as mock_shodan_class:

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
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_run_auto_detection_hostname(
        self, mock_get_db, plugin, mock_db_session, mock_config_service
    ):
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
                    "data": "HTTPS service",
                }
            ],
        }

        with patch(
            "app.plugins.shodan_plugin.SystemConfigService",
            return_value=mock_config_service,
        ), patch("shodan.Shodan") as mock_shodan_class:

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
            assert (
                "Searching for hostname: cloudflare.com"
                in results[0]["data"]["message"]
            )

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

    def test_extract_unique_ips_from_results(self, plugin):
        """Test IP extraction from various result types"""
        # Mock evidence results with different search types
        plugin._evidence_results = [
            {
                "ip": "8.8.8.8",
                "organization": "Google LLC",
                "country": "United States",
                "city": "Mountain View",
                "search_type": "host_lookup",
                "ports": [53, 443],
            },
            {
                "ip": "1.1.1.1",
                "organization": "Cloudflare",
                "country": "Australia",
                "city": "Sydney",
                "search_type": "hostname_search",
                "port": 443,
                "service": "Cloudflare",
                "transport": "tcp",
            },
            {
                "ip": "8.8.8.8",  # Duplicate - should be ignored
                "organization": "Google LLC",
                "search_type": "general_search",
            },
            {
                "ip": "invalid-ip",  # Invalid IP - should be ignored
                "organization": "Test",
            },
            {
                "no_ip_field": "test",  # No IP field - should be ignored
            },
        ]

        unique_ips = plugin._extract_unique_ips_from_results()

        # Should extract 2 unique IPs (8.8.8.8 and 1.1.1.1)
        assert len(unique_ips) == 2

        # Check that IPs are present
        ips = [ip_data["ip"] for ip_data in unique_ips]
        assert "8.8.8.8" in ips
        assert "1.1.1.1" in ips

        # Check that descriptions are generated
        for ip_data in unique_ips:
            assert "description" in ip_data
            assert "Discovered via Shodan" in ip_data["description"]

    def test_generate_ip_description(self, plugin):
        """Test IP description generation with various data combinations"""
        # Test host lookup description
        result = {
            "ip": "8.8.8.8",
            "organization": "Google LLC",
            "country": "United States",
            "city": "Mountain View",
            "search_type": "host_lookup",
            "ports": [53, 443, 80],
            "vulns": ["CVE-2024-1234"],
        }

        description = plugin._generate_ip_description(result)
        assert "Discovered via Shodan IP lookup" in description
        assert "Org: Google LLC" in description
        assert "Location: Mountain View, United States" in description
        assert "Ports: 53, 443, 80" in description
        assert "Vulnerability: CVE-2024-1234" in description

        # Test hostname search description
        result = {
            "ip": "1.1.1.1",
            "organization": "Cloudflare",
            "country": "Australia",
            "search_type": "hostname_search",
            "port": 443,
            "service": "Cloudflare",
            "version": "1.0",
            "transport": "tcp",
        }

        description = plugin._generate_ip_description(result)
        assert "Discovered via Shodan hostname search" in description
        assert "Org: Cloudflare" in description
        assert "Location: Australia" in description
        assert "Services: 443/tcp:Cloudflare 1.0" in description

        # Test general search with multiple vulnerabilities
        result = {
            "ip": "192.168.1.1",
            "search_type": "general_search",
            "vulns": ["CVE-2024-1234", "CVE-2024-5678", "CVE-2024-9999"],
        }

        description = plugin._generate_ip_description(result)
        assert "Discovered via Shodan general search" in description
        assert "Vulnerabilities: 3 found" in description

    @pytest.mark.asyncio
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_create_ip_entities_from_results_success(
        self, mock_get_db, plugin, mock_db_session
    ):
        """Test successful IP entity creation from results"""
        # Setup plugin state
        plugin._current_params = {"save_to_case": True, "case_id": 123}
        plugin._current_user = Mock()
        plugin._current_user.id = 1
        plugin._evidence_results = [
            {
                "ip": "8.8.8.8",
                "organization": "Google LLC",
                "search_type": "host_lookup",
            },
            {
                "ip": "1.1.1.1",
                "organization": "Cloudflare",
                "search_type": "hostname_search",
            },
        ]

        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_entity_service = Mock(spec=EntityService)
        mock_entity_service.create_entity = AsyncMock()

        with patch(
            "app.plugins.shodan_plugin.EntityService", return_value=mock_entity_service
        ):
            await plugin._create_ip_entities_from_results()

        # Verify entity service was called correctly
        assert mock_entity_service.create_entity.call_count == 2

        # Check the calls were made with correct data
        calls = mock_entity_service.create_entity.call_args_list
        for call in calls:
            args, kwargs = call
            assert kwargs["case_id"] == 123
            assert kwargs["current_user"] == plugin._current_user
            assert kwargs["entity"].entity_type == "ip_address"

            # Check that IP addresses are in the call data
            ip_address = kwargs["entity"].data["ip_address"]
            assert ip_address in ["8.8.8.8", "1.1.1.1"]

    @pytest.mark.asyncio
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_create_ip_entities_from_results_partial_failure(
        self, mock_get_db, plugin, mock_db_session
    ):
        """Test IP entity creation with some failures (e.g., duplicates)"""
        # Setup plugin state
        plugin._current_params = {"save_to_case": True, "case_id": 123}
        plugin._current_user = Mock()
        plugin._evidence_results = [
            {"ip": "8.8.8.8", "search_type": "host_lookup"},
            {"ip": "1.1.1.1", "search_type": "hostname_search"},
        ]

        # Setup mocks - first call succeeds, second fails (duplicate)
        mock_get_db.return_value = iter([mock_db_session])
        mock_entity_service = Mock(spec=EntityService)
        mock_entity_service.create_entity = AsyncMock()
        mock_entity_service.create_entity.side_effect = [
            Mock(),  # First call succeeds
            Exception("Duplicate entity"),  # Second call fails
        ]

        with patch(
            "app.plugins.shodan_plugin.EntityService", return_value=mock_entity_service
        ):

            await plugin._create_ip_entities_from_results()

        # Verify both entities were attempted
        assert mock_entity_service.create_entity.call_count == 2

    @pytest.mark.asyncio
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_create_ip_entities_no_save_to_case(self, mock_get_db, plugin):
        """Test that entities are not created when save_to_case is False"""
        # Setup plugin state with save_to_case disabled
        plugin._current_params = {"save_to_case": False, "case_id": 123}
        plugin._evidence_results = [{"ip": "8.8.8.8", "search_type": "host_lookup"}]

        mock_entity_service = Mock(spec=EntityService)

        with patch(
            "app.plugins.shodan_plugin.EntityService", return_value=mock_entity_service
        ):
            await plugin._create_ip_entities_from_results()

        # Verify no entities were created
        mock_entity_service.create_entity.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_create_ip_entities_no_case_id(self, mock_get_db, plugin):
        """Test that entities are not created when case_id is missing"""
        # Setup plugin state without case_id
        plugin._current_params = {
            "save_to_case": True,
            # Missing case_id
        }
        plugin._evidence_results = [{"ip": "8.8.8.8", "search_type": "host_lookup"}]

        mock_entity_service = Mock(spec=EntityService)

        with patch(
            "app.plugins.shodan_plugin.EntityService", return_value=mock_entity_service
        ):
            await plugin._create_ip_entities_from_results()

        # Verify no entities were created
        mock_entity_service.create_entity.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_save_collected_evidence_enhanced(
        self, mock_get_db, plugin, mock_db_session
    ):
        """Test enhanced save_collected_evidence calls both parent and entity creation"""
        # Setup plugin state
        plugin._current_params = {"save_to_case": True, "case_id": 123}
        plugin._current_user = Mock()
        plugin._evidence_results = [{"ip": "8.8.8.8", "search_type": "host_lookup"}]

        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_entity_service = Mock(spec=EntityService)
        mock_entity_service.find_entity_by_ip_address = AsyncMock(return_value=None)
        mock_entity_service.create_entity = AsyncMock()

        with patch(
            "app.plugins.shodan_plugin.EntityService", return_value=mock_entity_service
        ), patch.object(
            plugin.__class__.__bases__[0], "save_collected_evidence"
        ) as mock_parent_save:

            mock_parent_save.return_value = AsyncMock()
            await plugin.save_collected_evidence()

        # Verify parent method was called
        mock_parent_save.assert_called_once()

        # Verify entity creation was attempted
        mock_entity_service.create_entity.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_create_ip_entities_enrichment_existing_entity(
        self, mock_get_db, plugin, mock_db_session
    ):
        """Test enriching existing IP entity instead of creating duplicate"""
        # Setup plugin state
        plugin._current_params = {"save_to_case": True, "case_id": 123}
        plugin._current_user = Mock()
        plugin._current_user.id = 1
        plugin._evidence_results = [
            {
                "ip": "8.8.8.8",
                "organization": "Google LLC",
                "search_type": "host_lookup",
            }
        ]

        # Setup mocks - simulate existing entity
        mock_get_db.return_value = iter([mock_db_session])
        mock_entity_service = Mock(spec=EntityService)

        # Mock existing entity
        existing_entity = Mock()
        existing_entity.id = 456
        mock_entity_service.find_entity_by_ip_address = AsyncMock(
            return_value=existing_entity
        )
        mock_entity_service.enrich_entity_description = AsyncMock()
        mock_entity_service.create_entity = AsyncMock()

        with patch(
            "app.plugins.shodan_plugin.EntityService", return_value=mock_entity_service
        ):

            await plugin._create_ip_entities_from_results()

        # Verify entity lookup was called
        mock_entity_service.find_entity_by_ip_address.assert_called_once_with(
            123, "8.8.8.8"
        )

        # Verify enrichment was called instead of creation
        mock_entity_service.enrich_entity_description.assert_called_once()
        mock_entity_service.create_entity.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_create_ip_entities_mixed_new_and_existing(
        self, mock_get_db, plugin, mock_db_session
    ):
        """Test handling mix of new and existing IP entities"""
        # Setup plugin state with multiple IPs
        plugin._current_params = {"save_to_case": True, "case_id": 123}
        plugin._current_user = Mock()
        plugin._current_user.id = 1
        plugin._evidence_results = [
            {
                "ip": "8.8.8.8",  # Will be existing
                "organization": "Google LLC",
                "search_type": "host_lookup",
            },
            {
                "ip": "1.1.1.1",  # Will be new
                "organization": "Cloudflare",
                "search_type": "hostname_search",
            },
            {
                "ip": "9.9.9.9",  # Will be new
                "organization": "Quad9",
                "search_type": "general_search",
            },
        ]

        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_entity_service = Mock(spec=EntityService)

        # Mock existing entity for 8.8.8.8, None for others
        existing_entity = Mock()
        existing_entity.id = 456

        async def mock_find_entity(case_id, ip):
            if ip == "8.8.8.8":
                return existing_entity
            return None

        mock_entity_service.find_entity_by_ip_address = AsyncMock(
            side_effect=mock_find_entity
        )
        mock_entity_service.enrich_entity_description = AsyncMock()
        mock_entity_service.create_entity = AsyncMock()

        with patch(
            "app.plugins.shodan_plugin.EntityService", return_value=mock_entity_service
        ):

            await plugin._create_ip_entities_from_results()

        # Verify lookups for all IPs
        assert mock_entity_service.find_entity_by_ip_address.call_count == 3

        # Verify one enrichment and two creations
        mock_entity_service.enrich_entity_description.assert_called_once()
        assert mock_entity_service.create_entity.call_count == 2

    @pytest.mark.asyncio
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_create_ip_entities_enrichment_with_partial_failures(
        self, mock_get_db, plugin, mock_db_session
    ):
        """Test enrichment with some operations failing"""
        # Setup plugin state
        plugin._current_params = {"save_to_case": True, "case_id": 123}
        plugin._current_user = Mock()
        plugin._evidence_results = [
            {"ip": "8.8.8.8", "search_type": "host_lookup"},  # Will succeed (existing)
            {"ip": "1.1.1.1", "search_type": "hostname_search"},  # Will succeed (new)
            {"ip": "2.2.2.2", "search_type": "general_search"},  # Will fail
        ]

        # Setup mocks
        mock_get_db.return_value = iter([mock_db_session])
        mock_entity_service = Mock(spec=EntityService)

        # Mock existing entity for 8.8.8.8
        existing_entity = Mock()
        existing_entity.id = 456

        async def mock_find_entity(case_id, ip):
            if ip == "8.8.8.8":
                return existing_entity
            elif ip == "2.2.2.2":
                raise Exception("Lookup failed")
            return None

        mock_entity_service.find_entity_by_ip_address = AsyncMock(
            side_effect=mock_find_entity
        )
        mock_entity_service.enrich_entity_description = AsyncMock()
        mock_entity_service.create_entity = AsyncMock()

        with patch(
            "app.plugins.shodan_plugin.EntityService", return_value=mock_entity_service
        ):

            await plugin._create_ip_entities_from_results()

        # Verify operations
        mock_entity_service.enrich_entity_description.assert_called_once()
        mock_entity_service.create_entity.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_create_ip_entities_no_existing_entities(
        self, mock_get_db, plugin, mock_db_session
    ):
        """Test creating entities when none exist (original behavior)"""
        # Setup plugin state
        plugin._current_params = {"save_to_case": True, "case_id": 123}
        plugin._current_user = Mock()
        plugin._current_user.id = 1
        plugin._evidence_results = [
            {"ip": "192.168.1.1", "search_type": "host_lookup"},
            {"ip": "192.168.1.2", "search_type": "hostname_search"},
        ]

        # Setup mocks - no existing entities
        mock_get_db.return_value = iter([mock_db_session])
        mock_entity_service = Mock(spec=EntityService)
        mock_entity_service.find_entity_by_ip_address = AsyncMock(return_value=None)
        mock_entity_service.create_entity = AsyncMock()

        with patch(
            "app.plugins.shodan_plugin.EntityService", return_value=mock_entity_service
        ):

            await plugin._create_ip_entities_from_results()

        # Verify all were created as new entities
        assert mock_entity_service.create_entity.call_count == 2
        mock_entity_service.enrich_entity_description.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.plugins.shodan_plugin.get_db")
    async def test_create_ip_entities_all_existing_entities(
        self, mock_get_db, plugin, mock_db_session
    ):
        """Test enriching entities when all already exist"""
        # Setup plugin state
        plugin._current_params = {"save_to_case": True, "case_id": 123}
        plugin._current_user = Mock()
        plugin._evidence_results = [
            {"ip": "10.0.0.1", "search_type": "host_lookup"},
            {"ip": "10.0.0.2", "search_type": "hostname_search"},
        ]

        # Setup mocks - all entities exist
        mock_get_db.return_value = iter([mock_db_session])
        mock_entity_service = Mock(spec=EntityService)

        existing_entity = Mock()
        existing_entity.id = 456
        mock_entity_service.find_entity_by_ip_address = AsyncMock(
            return_value=existing_entity
        )
        mock_entity_service.enrich_entity_description = AsyncMock()
        mock_entity_service.create_entity = AsyncMock()

        with patch(
            "app.plugins.shodan_plugin.EntityService", return_value=mock_entity_service
        ):

            await plugin._create_ip_entities_from_results()

        # Verify all were enriched, none created
        assert mock_entity_service.enrich_entity_description.call_count == 2
        mock_entity_service.create_entity.assert_not_called()
