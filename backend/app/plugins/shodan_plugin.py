"""
Shodan plugin for searching hosts and services using Shodan API
"""

import time
from collections.abc import AsyncGenerator
from typing import Any

from app.services.api_key_vault import Provider

from .base_plugin import BasePlugin, PluginRun, ResultEvent
from .plugin_types import is_ip_address


class ShodanPlugin(BasePlugin):
    """Shodan plugin for searching hosts and services using Shodan API"""

    def __init__(self):
        super().__init__(display_name="Shodan Search")
        self.description = (
            "Search for hosts and services using Shodan's comprehensive database"
        )
        self.category = "Network"
        self.evidence_category = "Network Assets"
        self.api_key_requirements = [Provider.SHODAN]
        self.parameters = {
            "query": {
                "type": "string",
                "description": "Search query (IP address, hostname, or Shodan query syntax)",
                "required": True,
            },
            "search_type": {
                "type": "string",
                "description": "Type of search to perform",
                "default": "general",
                "required": False,
            },
            "limit": {
                "type": "float",
                "description": "Maximum number of results to return (1-100)",
                "default": 10.0,
                "required": False,
            },
        }

    def _is_hostname(self, value: str) -> bool:
        """Check if the given value appears to be a hostname"""
        return "." in value and (not is_ip_address(value))

    async def _search_shodan(
        self, api_key: str, query: str, search_type: str, limit: int
    ) -> AsyncGenerator[ResultEvent, None]:
        """
        Perform Shodan search with the given parameters

        Args:
            api_key: Shodan API key
            query: Search query
            search_type: Type of search (ip, hostname, general)
            limit: Maximum results to return

        Yields:
            Structured search results or errors
        """
        try:
            import shodan

            api = shodan.Shodan(api_key)
            if search_type == "ip" or (
                search_type == "general" and is_ip_address(query)
            ):
                yield self.status(f"Looking up IP: {query}")
                try:
                    host_info = api.host(query)
                    yield self.data(
                        {
                            "ip": host_info.get("ip_str"),
                            "hostnames": host_info.get("hostnames", []),
                            "organization": host_info.get("org", "Unknown"),
                            "country": host_info.get("country_name", "Unknown"),
                            "city": host_info.get("city", "Unknown"),
                            "ports": host_info.get("ports", []),
                            "last_update": host_info.get("last_update", "Unknown"),
                            "vulns": list(host_info.get("vulns", [])),
                            "services": [
                                {
                                    "port": service.get("port"),
                                    "transport": service.get("transport", "tcp"),
                                    "service": service.get("product", "Unknown"),
                                    "version": service.get("version", ""),
                                    "banner": (
                                        service.get("data", "")[:200] + "..."
                                        if len(service.get("data", "")) > 200
                                        else service.get("data", "")
                                    ),
                                }
                                for service in host_info.get("data", [])
                            ],
                            "search_type": "host_lookup",
                            "timestamp": time.time(),
                        }
                    )
                except shodan.APIError as e:
                    if "No information available" in str(e):
                        yield self.error(
                            f"No information available for IP {query} in Shodan database"
                        )
                    else:
                        yield self.error(f"Shodan API error for IP {query}: {e!s}")
            elif search_type == "hostname" or (
                search_type == "general" and self._is_hostname(query)
            ):
                yield self.status(f"Searching for hostname: {query}")
                try:
                    results = api.search(
                        f"hostname:{query}", limit=min(int(limit), 100)
                    )
                    if results["total"] == 0:
                        yield self.error(f"No results found for hostname: {query}")
                    else:
                        for match in results["matches"]:
                            yield self.data(
                                {
                                    "ip": match.get("ip_str"),
                                    "hostnames": match.get("hostnames", []),
                                    "organization": match.get("org", "Unknown"),
                                    "country": match.get("location", {}).get(
                                        "country_name", "Unknown"
                                    ),
                                    "city": match.get("location", {}).get(
                                        "city", "Unknown"
                                    ),
                                    "port": match.get("port"),
                                    "transport": match.get("transport", "tcp"),
                                    "service": match.get("product", "Unknown"),
                                    "version": match.get("version", ""),
                                    "banner": (
                                        match.get("data", "")[:200] + "..."
                                        if len(match.get("data", "")) > 200
                                        else match.get("data", "")
                                    ),
                                    "last_update": match.get("timestamp", "Unknown"),
                                    "search_type": "hostname_search",
                                    "timestamp": time.time(),
                                }
                            )
                except shodan.APIError as e:
                    yield self.error(f"Shodan API error for hostname {query}: {e!s}")
            else:
                yield self.status(f"Searching Shodan: {query}")
                try:
                    results = api.search(query, limit=min(int(limit), 100))
                    if results["total"] == 0:
                        yield self.error(f"No results found for query: {query}")
                    else:
                        yield self.status(
                            f"Found {results['total']} results (showing {len(results['matches'])})"
                        )
                        for match in results["matches"]:
                            yield self.data(
                                {
                                    "ip": match.get("ip_str"),
                                    "hostnames": match.get("hostnames", []),
                                    "organization": match.get("org", "Unknown"),
                                    "country": match.get("location", {}).get(
                                        "country_name", "Unknown"
                                    ),
                                    "city": match.get("location", {}).get(
                                        "city", "Unknown"
                                    ),
                                    "port": match.get("port"),
                                    "transport": match.get("transport", "tcp"),
                                    "service": match.get("product", "Unknown"),
                                    "version": match.get("version", ""),
                                    "banner": (
                                        match.get("data", "")[:200] + "..."
                                        if len(match.get("data", "")) > 200
                                        else match.get("data", "")
                                    ),
                                    "last_update": match.get("timestamp", "Unknown"),
                                    "vulns": list(match.get("vulns", [])),
                                    "search_type": "general_search",
                                    "timestamp": time.time(),
                                }
                            )
                except shodan.APIError as e:
                    if "Invalid API key" in str(e):
                        yield self.error(
                            "Invalid Shodan API key. Please check your API key in Admin → Configuration → API Keys"
                        )
                    elif "API rate limit" in str(e) or "rate limited" in str(e):
                        yield self.error(
                            "Shodan API rate limit exceeded. Please wait before making more requests"
                        )
                    elif (
                        "Query credits" in str(e)
                        or "insufficient query credits" in str(e).lower()
                    ):
                        yield self.error(
                            "Insufficient Shodan query credits. Please check your account plan"
                        )
                    else:
                        yield self.error(f"Shodan API error: {e!s}")
        except ImportError:
            yield self.error(
                "Shodan library not installed. Please install the 'shodan' package"
            )
        except Exception as e:
            yield self.error(f"Unexpected error during Shodan search: {e!s}")

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        """
        Execute Shodan search with given parameters

        Args:
            params: Dictionary of search parameters

        Yields:
            Dictionary containing search results or errors
        """
        if not params or "query" not in params:
            yield self.error("Search query parameter is required")
            return
        query = params["query"].strip()
        search_type = params.get("search_type", "general")
        limit = min(max(int(params.get("limit", 10)), 1), 100)
        if not query:
            yield self.error("Search query cannot be empty")
            return
        shodan_api_key = ctx.key(Provider.SHODAN)
        if not shodan_api_key:
            yield ctx.missing_key(Provider.SHODAN)
            return
        try:
            if search_type == "general":
                if is_ip_address(query):
                    search_type = "ip"
                elif self._is_hostname(query):
                    search_type = "hostname"
            async for result in self._search_shodan(
                shodan_api_key, query, search_type, limit
            ):
                yield result
        except Exception as e:
            yield self.error(f"Unexpected error during Shodan search: {e!s}")

    def entity_writes(self, payloads, params):
        """Extract unique IP addresses with metadata from collected results"""
        candidates = []
        original_query = params.get("query", "")
        for result in payloads:
            ip_address = result.get("ip")
            description = self._generate_ip_description_from_shodan_result(
                result, original_query
            )
            candidates.append(
                (ip_address, description, {"ip_address": "Shodan Search"})
            )
        from .base_plugin import unique_ip_writes

        return unique_ip_writes(candidates)

    def _generate_ip_description_from_shodan_result(
        self, result: dict, original_query: str = ""
    ) -> str:
        """Generate a descriptive string for the IP address entity based on Shodan result"""
        search_type = result.get("search_type", "unknown")
        if search_type == "host_lookup":
            context = (
                f"IP lookup for '{original_query}'" if original_query else "IP lookup"
            )
        elif search_type == "hostname_search":
            context = (
                f"hostname lookup for '{original_query}'"
                if original_query
                else "hostname lookup"
            )
        elif search_type == "general_search":
            context = (
                f"general lookup for '{original_query}'"
                if original_query
                else "general lookup"
            )
        else:
            context = f"lookup for '{original_query}'" if original_query else "lookup"
        return self._generate_ip_description("", context)
