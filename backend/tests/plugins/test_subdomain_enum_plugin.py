"""
Tests for Subdomain Enumeration plugin
"""

import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from app.plugins.subdomain_enum_plugin import SubdomainEnumPlugin

class TestSubdomainEnumPlugin:
    """Test cases for SubdomainEnumPlugin"""

    @pytest.fixture
    def plugin(self):
        """Create plugin instance for testing"""
        return SubdomainEnumPlugin()

    def test_plugin_initialization(self, plugin):
        """Test plugin initializes correctly"""
        assert plugin.display_name == "Subdomain Enumeration"
        assert plugin.description == "Enumerate subdomains via Certificate Transparency logs, HackerTarget, and SecurityTrails with DNS verification"
        assert plugin.category == "Network"
        assert plugin.evidence_category == "Network Assets"
        assert "save_to_case" in plugin.parameters

    def test_plugin_parameters(self, plugin):
        """Test plugin parameters are defined correctly"""
        assert isinstance(plugin.parameters, dict)
        assert "domain" in plugin.parameters
        assert plugin.parameters["domain"]["required"] is True
        assert plugin.parameters["domain"]["type"] == "string"
        
        assert "concurrency" in plugin.parameters
        assert plugin.parameters["concurrency"]["required"] is False
        assert plugin.parameters["concurrency"]["default"] == 50.0
        
        assert "use_securitytrails" in plugin.parameters
        assert plugin.parameters["use_securitytrails"]["required"] is False
        assert plugin.parameters["use_securitytrails"]["type"] == "boolean"

    @pytest.mark.asyncio
    async def test_plugin_run_missing_params(self, plugin):
        """Test plugin handles missing parameters correctly"""
        results = []
        async for result in plugin.run(None):
            results.append(result)
        
        assert len(results) == 1
        assert results[0]["type"] == "error"
        assert "required" in results[0]["data"]["message"].lower()

    @pytest.mark.asyncio
    async def test_plugin_run_empty_params(self, plugin):
        """Test plugin handles empty parameters correctly"""
        results = []
        async for result in plugin.run({}):
            results.append(result)
        
        assert len(results) == 1
        assert results[0]["type"] == "error"

    @pytest.mark.asyncio
    async def test_plugin_run_valid_params(self, plugin):
        """Test plugin with valid parameters"""
        # Mock the API responses
        mock_crt_response = json.dumps([
            {"name_value": "api.example.com\nwww.example.com"},
            {"name_value": "test.example.com"}
        ])
        
        mock_ht_response = "api.example.com,192.168.1.1\nmail.example.com,192.168.1.2"
        
        # Mock DNS resolution
        mock_resolver = MagicMock()
        mock_answer = MagicMock()
        mock_answer.to_text.return_value = "192.168.1.1"
        
        with patch('aiohttp.ClientSession') as mock_session:
            # Setup mock responses
            mock_resp_crt = AsyncMock()
            mock_resp_crt.text.return_value = mock_crt_response
            
            mock_resp_ht = AsyncMock()
            mock_resp_ht.text.return_value = mock_ht_response
            
            mock_session.return_value.__aenter__.return_value.get.side_effect = [
                mock_resp_crt,
                mock_resp_ht
            ]
            
            with patch('dns.asyncresolver.Resolver') as mock_resolver_class:
                mock_resolver_instance = MagicMock()
                mock_resolver_instance.resolve = AsyncMock(return_value=[mock_answer])
                mock_resolver_class.return_value = mock_resolver_instance
                
                params = {"domain": "example.com", "concurrency": 10}
                results = []
                async for result in plugin.run(params):
                    results.append(result)
                
                # Check we got results
                assert len(results) > 0
                
                # Check for status messages
                status_messages = [r for r in results if r.get("data", {}).get("phase") in ["discovery", "resolution"]]
                assert len(status_messages) > 0
                
                # Check for subdomain results
                subdomain_results = [r for r in results if r.get("data", {}).get("subdomain")]
                assert len(subdomain_results) > 0

    @pytest.mark.asyncio 
    async def test_plugin_run_with_securitytrails(self, plugin):
        """Test plugin with SecurityTrails enabled but no API key"""
        params = {"domain": "example.com", "use_securitytrails": True}
        results = []
        
        async for result in plugin.run(params):
            results.append(result)
            # Stop after first error
            if result["type"] == "error":
                break
        
        assert results[0]["type"] == "error"
        assert "SecurityTrails API key" in results[0]["data"]["message"]

    @pytest.mark.asyncio
    async def test_plugin_fetch_methods(self, plugin):
        """Test individual fetch methods handle errors gracefully"""
        # Test fetch_from_crt with invalid response
        with patch('aiohttp.ClientSession') as mock_session:
            mock_resp = AsyncMock()
            mock_resp.text.return_value = "invalid json"
            mock_session.return_value.__aenter__.return_value.get.return_value = mock_resp
            
            result = await plugin.fetch_from_crt("example.com")
            assert result == set()
        
        # Test fetch_from_hackertarget with connection error
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.side_effect = Exception("Connection error")
            
            result = await plugin.fetch_from_hackertarget("example.com")
            assert result == set()

    def test_format_evidence_content(self, plugin):
        """Test evidence formatting"""
        results = [
            {"type": "data", "data": {"subdomain": "api.example.com", "ip": "192.168.1.1", "resolved": True, "source": "crt.sh"}},
            {"type": "data", "data": {"subdomain": "www.example.com", "ip": "192.168.1.2", "resolved": True, "source": "HackerTarget"}},
            {"type": "data", "data": {"status": "complete", "phase": "summary", "total_discovered": 2, "total_resolved": 2, "sources_used": ["crt.sh", "HackerTarget"]}}
        ]
        params = {
            "domain": "example.com",
            "execution_time": "2024-01-01 12:00:00"
        }
        
        content = plugin._format_evidence_content(results, params)
        assert isinstance(content, str)
        assert "example.com" in content
        assert "api.example.com" in content
        assert "192.168.1.1" in content
        assert "Total Unique Subdomains Found: 2" in content

    def test_plugin_metadata(self, plugin):
        """Test plugin metadata is properly set"""
        assert plugin.display_name
        assert plugin.description  
        assert plugin.category in ["Person", "Network", "Company", "Other"]
        assert plugin.evidence_category in [
            "Social Media", "Associates", "Network Assets", 
            "Communications", "Documents", "Other"
        ]
