"""
DNS lookup plugin for resolving domain names to IP addresses
"""

from typing import AsyncGenerator, Dict, Any, Optional
import json
import dns.asyncresolver
from dns.rdatatype import RdataType
from dns.exception import DNSException

from .base_plugin import BasePlugin


class DnsLookup(BasePlugin):
    """DNS lookup plugin for resolving domain names to IP addresses"""

    def __init__(self):
        super().__init__(display_name="DNS Lookup")
        self.description = "Resolves domain names to their IP addresses"
        self.category = "Network"
        self.save_to_case = False
        self.parameters = {
            "domain": {
                "type": "string",
                "description": "Domain name to resolve",
                "required": True,
            },
            "timeout": {
                "type": "float",
                "description": "Query timeout in seconds",
                "default": 5.0,
                "required": False,
            },
        }

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Not used as DNS queries are handled directly"""
        return None

    async def _perform_lookup(
        self,
        resolver: dns.asyncresolver.Resolver,
        domain: str,
    ) -> Dict[str, Any]:
        """
        Perform DNS A record lookup

        Args:
            resolver: DNS resolver instance
            domain: Domain name to query

        Returns:
            Dictionary containing IP addresses or error
        """
        try:
            answers = await resolver.resolve(domain, RdataType.A)
            return json.loads(
                json.dumps(
                    {"domain": domain, "ips": [answer.to_text() for answer in answers]}
                )
            )
        except DNSException as e:
            return json.loads(
                json.dumps({"domain": domain, "error": f"DNS error: {str(e)}"})
            )
        except Exception as e:
            return json.loads(
                json.dumps({"domain": domain, "error": f"Unexpected error: {str(e)}"})
            )

    async def run(
        self,
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute DNS lookup with given parameters

        Args:
            params: Dictionary of query parameters

        Yields:
            Dictionary containing IP addresses or error
        """
        if not params or "domain" not in params:
            yield json.loads(json.dumps({"error": "Domain parameter is required"}))
            return

        domain = params["domain"]
        timeout = params.get("timeout", 5.0)

        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout * 2

        result = await self._perform_lookup(resolver, domain)
        yield result
