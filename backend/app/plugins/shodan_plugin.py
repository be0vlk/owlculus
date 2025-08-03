"""
Shodan plugin for searching hosts and services using Shodan API

Key features include:
- Multi-mode search supporting IP lookup, hostname search, and general Shodan queries
- Comprehensive host intelligence with service enumeration and vulnerability detection
- Automatic search type detection based on input format (IP, hostname, or query)
- Detailed service banner extraction with port, protocol, and version information
- Custom IP entity creation with rich Shodan context and geolocation metadata
"""

import time
from typing import Any, AsyncGenerator, Dict, Optional

from app.core.dependencies import get_db
from app.services.system_config_service import SystemConfigService
from sqlmodel import Session

from .base_plugin import BasePlugin


class ShodanPlugin(BasePlugin):
    """Shodan plugin for searching hosts and services using Shodan API"""

    def __init__(self, db_session: Session = None):
        super().__init__(display_name="Shodan Search", db_session=db_session)
        self.description = (
            "Search for hosts and services using Shodan's comprehensive database"
        )
        self.category = "Network"
        self.evidence_category = "Network Assets"
        self.save_to_case = False
        self.api_key_requirements = ["shodan"]
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

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Not used as Shodan queries are handled directly via API"""
        return None

    def _is_hostname(self, value: str) -> bool:
        """Check if the given value appears to be a hostname"""
        return "." in value and not self._is_ip_address(value)

    async def _search_shodan(
        self, api_key: str, query: str, search_type: str, limit: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
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

            # Initialize Shodan API client
            api = shodan.Shodan(api_key)

            # Determine search strategy based on type and query
            if search_type == "ip" or (
                search_type == "general" and self._is_ip_address(query)
            ):
                # Direct IP lookup using host() method
                yield {"type": "status", "data": {"message": f"Looking up IP: {query}"}}

                try:
                    host_info = api.host(query)
                    yield {
                        "type": "data",
                        "data": {
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
                        },
                    }
                except shodan.APIError as e:
                    if "No information available" in str(e):
                        yield {
                            "type": "error",
                            "data": {
                                "message": f"No information available for IP {query} in Shodan database"
                            },
                        }
                    else:
                        yield {
                            "type": "error",
                            "data": {
                                "message": f"Shodan API error for IP {query}: {str(e)}"
                            },
                        }

            elif search_type == "hostname" or (
                search_type == "general" and self._is_hostname(query)
            ):
                # Hostname search - first resolve then search
                yield {
                    "type": "status",
                    "data": {"message": f"Searching for hostname: {query}"},
                }

                try:
                    results = api.search(
                        f"hostname:{query}", limit=min(int(limit), 100)
                    )

                    if results["total"] == 0:
                        yield {
                            "type": "error",
                            "data": {
                                "message": f"No results found for hostname: {query}"
                            },
                        }
                    else:
                        for match in results["matches"]:
                            yield {
                                "type": "data",
                                "data": {
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
                                },
                            }
                except shodan.APIError as e:
                    yield {
                        "type": "error",
                        "data": {
                            "message": f"Shodan API error for hostname {query}: {str(e)}"
                        },
                    }

            else:
                # General search using Shodan query syntax
                yield {
                    "type": "status",
                    "data": {"message": f"Searching Shodan: {query}"},
                }

                try:
                    results = api.search(query, limit=min(int(limit), 100))

                    if results["total"] == 0:
                        yield {
                            "type": "error",
                            "data": {"message": f"No results found for query: {query}"},
                        }
                    else:
                        yield {
                            "type": "status",
                            "data": {
                                "message": f"Found {results['total']} results (showing {len(results['matches'])})"
                            },
                        }

                        for match in results["matches"]:
                            yield {
                                "type": "data",
                                "data": {
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
                                },
                            }
                except shodan.APIError as e:
                    if "Invalid API key" in str(e):
                        yield {
                            "type": "error",
                            "data": {
                                "message": "Invalid Shodan API key. Please check your API key in Admin → Configuration → API Keys"
                            },
                        }
                    elif "API rate limit" in str(e) or "rate limited" in str(e):
                        yield {
                            "type": "error",
                            "data": {
                                "message": "Shodan API rate limit exceeded. Please wait before making more requests"
                            },
                        }
                    elif (
                        "Query credits" in str(e)
                        or "insufficient query credits" in str(e).lower()
                    ):
                        yield {
                            "type": "error",
                            "data": {
                                "message": "Insufficient Shodan query credits. Please check your account plan"
                            },
                        }
                    else:
                        yield {
                            "type": "error",
                            "data": {"message": f"Shodan API error: {str(e)}"},
                        }

        except ImportError:
            yield {
                "type": "error",
                "data": {
                    "message": "Shodan library not installed. Please install the 'shodan' package"
                },
            }
        except Exception as e:
            yield {
                "type": "error",
                "data": {"message": f"Unexpected error during Shodan search: {str(e)}"},
            }

    async def run(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute Shodan search with given parameters

        Args:
            params: Dictionary of search parameters

        Yields:
            Dictionary containing search results or errors
        """
        if not params or "query" not in params:
            yield {
                "type": "error",
                "data": {"message": "Search query parameter is required"},
            }
            return

        # Extract parameters
        query = params["query"].strip()
        search_type = params.get("search_type", "general")
        limit = min(max(int(params.get("limit", 10)), 1), 100)  # Clamp between 1-100

        if not query:
            yield {"type": "error", "data": {"message": "Search query cannot be empty"}}
            return

        # Use injected session if available, otherwise get a new one
        if self._db_session:
            db = self._db_session
            close_session = False
        else:
            db = next(get_db())
            close_session = True

        try:
            # Retrieve Shodan API key using the centralized system
            config_service = SystemConfigService(db)
            shodan_api_key = config_service.get_api_key("shodan")

            if not shodan_api_key:
                yield {
                    "type": "error",
                    "data": {
                        "message": "Shodan API key not configured. Please add it in Admin → Configuration → API Keys"
                    },
                }
                return

            # Auto-detect search type if set to general
            if search_type == "general":
                if self._is_ip_address(query):
                    search_type = "ip"
                elif self._is_hostname(query):
                    search_type = "hostname"

            # Perform the search
            async for result in self._search_shodan(
                shodan_api_key, query, search_type, limit
            ):
                yield result

        except Exception as e:
            yield {
                "type": "error",
                "data": {"message": f"Database error: {str(e)}"},
            }
        finally:
            # Only close if we created the session
            if close_session:
                db.close()

    def _extract_unique_ips_from_results(self) -> list[dict]:
        """Extract unique IP addresses with metadata from collected results"""
        ip_data_map = {}  # Use dict to avoid duplicates while preserving rich data

        # Get the original query from current params
        original_query = (
            self._current_params.get("query", "") if self._current_params else ""
        )

        for result in self._evidence_results:
            ip_address = result.get("ip")
            if not ip_address or not self._is_ip_address(ip_address):
                continue

            # Skip if we already have this IP with better data
            if ip_address in ip_data_map:
                continue

            # Generate description based on available Shodan data
            description = self._generate_ip_description_from_shodan_result(
                result, original_query
            )

            ip_data_map[ip_address] = {
                "ip": ip_address,
                "description": description,
                "sources": {"ip_address": "Shodan Search"},
            }

        return list(ip_data_map.values())

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
