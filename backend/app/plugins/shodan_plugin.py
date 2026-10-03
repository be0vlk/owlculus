"""
Shodan plugin for searching hosts and services using Shodan API
"""

import time
from collections.abc import AsyncGenerator
from typing import Any

import shodan

from app.services.api_key_vault import Provider

from .base_plugin import BasePlugin, PluginRun, ResultEvent
from .plugin_types import is_ip_address, unique_ip_writes


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
        """Look up an IP, or search Shodan for a hostname or raw query."""
        api = shodan.Shodan(api_key)
        if search_type == "ip":
            yield self.status(f"Looking up IP: {query}")
            try:
                host_info = api.host(query)
            except shodan.APIError as e:
                if "No information available" in str(e):
                    yield self.error(
                        f"No information available for IP {query} in Shodan database"
                    )
                else:
                    yield self.error(f"Shodan API error for IP {query}: {e!s}")
                return
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
                            "banner": _banner(service),
                        }
                        for service in host_info.get("data", [])
                    ],
                    "search_type": "host_lookup",
                    "timestamp": time.time(),
                }
            )
            return

        hostname = search_type == "hostname"
        yield self.status(
            f"Searching for hostname: {query}"
            if hostname
            else f"Searching Shodan: {query}"
        )
        try:
            results = api.search(
                f"hostname:{query}" if hostname else query, limit=limit
            )
        except shodan.APIError as e:
            message = str(e)
            if hostname:
                yield self.error(f"Shodan API error for hostname {query}: {message}")
            elif "Invalid API key" in message:
                yield self.error(
                    "Invalid Shodan API key. Please check your API key in Admin → Configuration → API Keys"
                )
            elif "API rate limit" in message or "rate limited" in message:
                yield self.error(
                    "Shodan API rate limit exceeded. Please wait before making more requests"
                )
            elif (
                "Query credits" in message
                or "insufficient query credits" in message.lower()
            ):
                yield self.error(
                    "Insufficient Shodan query credits. Please check your account plan"
                )
            else:
                yield self.error(f"Shodan API error: {message}")
            return
        if results["total"] == 0:
            label = "hostname" if hostname else "query"
            yield self.error(f"No results found for {label}: {query}")
            return
        if not hostname:
            yield self.status(
                f"Found {results['total']} results (showing {len(results['matches'])})"
            )
        for match in results["matches"]:
            yield self.data(
                _match_payload(
                    match, "hostname_search" if hostname else "general_search"
                )
            )

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
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
        if search_type == "general":
            if is_ip_address(query):
                search_type = "ip"
            elif self._is_hostname(query):
                search_type = "hostname"
        try:
            async for result in self._search_shodan(
                shodan_api_key, query, search_type, limit
            ):
                yield result
        except Exception as e:
            yield self.error(f"Unexpected error during Shodan search: {e!s}")

    def entity_writes(self, payloads, params):
        """Extract unique IP addresses with metadata from collected results"""
        query = params.get("query", "")
        candidates = []
        for result in payloads:
            context = _LOOKUP_CONTEXTS.get(result.get("search_type"), "lookup")
            if query:
                context += f" for '{query}'"
            candidates.append(
                (
                    result.get("ip"),
                    self._generate_ip_description(context),
                    {"ip_address": "Shodan Search"},
                )
            )
        return unique_ip_writes(candidates)


_LOOKUP_CONTEXTS = {
    "host_lookup": "IP lookup",
    "hostname_search": "hostname lookup",
    "general_search": "general lookup",
}


def _banner(item: dict[str, Any]) -> str:
    data = item.get("data", "")
    return data[:200] + "..." if len(data) > 200 else data


def _match_payload(match: dict[str, Any], search_type: str) -> dict[str, Any]:
    location = match.get("location", {})
    return {
        "ip": match.get("ip_str"),
        "hostnames": match.get("hostnames", []),
        "organization": match.get("org", "Unknown"),
        "country": location.get("country_name", "Unknown"),
        "city": location.get("city", "Unknown"),
        "port": match.get("port"),
        "transport": match.get("transport", "tcp"),
        "service": match.get("product", "Unknown"),
        "version": match.get("version", ""),
        "banner": _banner(match),
        "last_update": match.get("timestamp", "Unknown"),
        "vulns": list(match.get("vulns", [])),
        "search_type": search_type,
        "timestamp": time.time(),
    }
