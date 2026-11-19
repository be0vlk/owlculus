"""
DNS lookup plugin for resolving domain names to IP addresses and performing reverse DNS lookups
"""

import asyncio
import time
from collections.abc import AsyncGenerator
from typing import Any

import dns.asyncresolver
from dns.exception import DNSException
from dns.rdatatype import RdataType
from dns.reversename import from_address

from .base_plugin import BasePlugin, PluginRun, ResultEvent
from .plugin_types import is_ip_address, unique_ip_writes


class DnsLookup(BasePlugin):
    """DNS lookup plugin for resolving domain names to IP addresses and performing reverse DNS lookups"""

    def __init__(self):
        super().__init__(display_name="DNS Lookup")
        self.description = "Resolves domain names to IP addresses and performs reverse DNS lookups for IP addresses"
        self.category = "Network"
        self.evidence_category = "Network Assets"
        self.parameters = {
            "domain": {
                "type": "string",
                "description": "Domain name or IP address to resolve (or comma-separated list for bulk lookup)",
                "required": True,
            },
            "lookup_mode": {
                "type": "string",
                "description": "Lookup mode: 'forward' for domain to IP, 'reverse' for IP to domain",
                "default": "forward",
                "required": False,
            },
            "record_types": {
                "type": "string",
                "description": "Comma-separated DNS record types (A,AAAA,MX,TXT,NS,CNAME) - only used for forward lookups",
                "default": "A",
                "required": False,
            },
            "timeout": {
                "type": "float",
                "description": "Query timeout in seconds",
                "default": 5.0,
                "required": False,
            },
            "nameservers": {
                "type": "string",
                "description": "Comma-separated custom DNS servers (e.g., 8.8.8.8,1.1.1.1)",
                "required": False,
            },
        }

    async def _perform_reverse_lookup(
        self, resolver: dns.asyncresolver.Resolver, ip_address: str
    ) -> dict[str, Any]:
        """Resolve the PTR records for an IP address."""
        try:
            answers = await resolver.resolve(from_address(ip_address), RdataType.PTR)
            records = [answer.to_text().rstrip(".") for answer in answers]
            return {"ip_address": ip_address, "type": "PTR", "records": records}
        except Exception as e:
            prefix = (
                "Reverse DNS error"
                if isinstance(e, DNSException)
                else "Unexpected error"
            )
            return {
                "ip_address": ip_address,
                "type": "PTR",
                "error": f"{prefix}: {e!s}",
            }

    async def _perform_single_lookup(
        self, resolver: dns.asyncresolver.Resolver, domain: str, record_type: str
    ) -> dict[str, Any]:
        """Resolve one record type for a domain."""
        try:
            rdata_type = getattr(RdataType, record_type.upper())
            answers = await resolver.resolve(domain, rdata_type)
            if record_type.upper() == "MX":
                records = [
                    f"{answer.preference} {answer.exchange}" for answer in answers
                ]
            elif record_type.upper() == "TXT":
                records = [str(answer).strip('"') for answer in answers]
            else:
                records = [answer.to_text() for answer in answers]
            return {"domain": domain, "type": record_type, "records": records}
        except Exception as e:
            prefix = "DNS error" if isinstance(e, DNSException) else "Unexpected error"
            return {"domain": domain, "type": record_type, "error": f"{prefix}: {e!s}"}

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        if not params or "domain" not in params:
            yield self.error("Domain parameter is required")
            return
        domains_param = params["domain"]
        targets = [d.strip() for d in domains_param.split(",") if d.strip()]
        lookup_mode = params.get("lookup_mode", "forward")
        record_types_param = params.get("record_types", "A")
        record_types = [
            rt.strip().upper() for rt in record_types_param.split(",") if rt.strip()
        ]
        timeout = params.get("timeout", 5.0)
        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout * 2
        if params.get("nameservers"):
            nameservers = [
                ns.strip() for ns in params["nameservers"].split(",") if ns.strip()
            ]
            resolver.nameservers = nameservers
        for target in targets:
            if lookup_mode == "reverse":
                if not is_ip_address(target):
                    yield self.error(
                        f"'{target}' is not a valid IP address for reverse lookup"
                    )
                    continue
                result = await self._perform_reverse_lookup(resolver, target)
                yield self.data(
                    {
                        "target": target,
                        "target_type": "ip_address",
                        "results": [result],
                        "timestamp": time.time(),
                    }
                )
            else:
                if is_ip_address(target):
                    yield self.error(
                        f"'{target}' appears to be an IP address. Use reverse lookup mode for IP addresses."
                    )
                    continue
                results = await asyncio.gather(
                    *(
                        self._perform_single_lookup(resolver, target, record_type)
                        for record_type in record_types
                    )
                )
                yield self.data(
                    {
                        "target": target,
                        "target_type": "domain",
                        "results": results,
                        "timestamp": time.time(),
                    }
                )

    def entity_writes(self, payloads, params):
        """Extract unique IP addresses with metadata from collected DNS results"""
        return unique_ip_writes(
            (
                record,
                self._generate_ip_description(
                    f"{payload.get('target', '')} ({result.get('type')} record)"
                ),
                {"ip_address": "DNS Lookup"},
            )
            for payload in payloads
            for result in payload.get("results", [])
            if result.get("type") in {"A", "AAAA"}
            for record in result.get("records", [])
        )
