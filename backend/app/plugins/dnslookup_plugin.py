"""
DNS lookup plugin for resolving domain names to IP addresses and performing reverse DNS lookups
"""

from typing import AsyncGenerator, Dict, Any, Optional, List
import asyncio
import time
import ipaddress
import dns.asyncresolver
from dns.rdatatype import RdataType
from sqlmodel import Session
from dns.exception import DNSException
from dns.reversename import from_address

from .base_plugin import BasePlugin


class DnsLookup(BasePlugin):
    """DNS lookup plugin for resolving domain names to IP addresses and performing reverse DNS lookups"""

    def __init__(self, db_session: Session = None):
        super().__init__(display_name="DNS Lookup", db_session=db_session)
        self.description = "Resolves domain names to IP addresses and performs reverse DNS lookups for IP addresses"
        self.category = "Network"
        self.evidence_category = "Network Assets"
        self.save_to_case = False
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

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Not used as DNS queries are handled directly"""
        return None

    def _is_ip_address(self, value: str) -> bool:
        """Check if the given value is a valid IP address"""
        try:
            ipaddress.ip_address(value)
            return True
        except ValueError:
            return False

    async def _perform_reverse_lookup(
        self,
        resolver: dns.asyncresolver.Resolver,
        ip_address: str,
    ) -> Dict[str, Any]:
        """
        Perform reverse DNS lookup for an IP address

        Args:
            resolver: DNS resolver instance
            ip_address: IP address to perform reverse lookup on

        Returns:
            Dictionary containing reverse lookup results or error
        """
        try:
            # Create reverse DNS query name
            reverse_name = from_address(ip_address)
            answers = await resolver.resolve(reverse_name, RdataType.PTR)

            # Extract hostnames from PTR records
            records = [answer.to_text().rstrip(".") for answer in answers]

            return {
                "ip_address": ip_address,
                "type": "PTR",
                "records": records,
            }
        except DNSException as e:
            return {
                "ip_address": ip_address,
                "type": "PTR",
                "error": f"Reverse DNS error: {str(e)}",
            }
        except Exception as e:
            return {
                "ip_address": ip_address,
                "type": "PTR",
                "error": f"Unexpected error: {str(e)}",
            }

    async def _perform_single_lookup(
        self,
        resolver: dns.asyncresolver.Resolver,
        domain: str,
        record_type: str,
    ) -> Dict[str, Any]:
        """
        Perform a single DNS lookup for a specific record type

        Args:
            resolver: DNS resolver instance
            domain: Domain name to query
            record_type: DNS record type (A, AAAA, MX, etc.)

        Returns:
            Dictionary containing query results or error
        """
        try:
            rdata_type = getattr(RdataType, record_type.upper())
            answers = await resolver.resolve(domain, rdata_type)

            # Format results based on record type
            if record_type.upper() == "MX":
                records = [
                    f"{answer.preference} {answer.exchange}" for answer in answers
                ]
            elif record_type.upper() == "TXT":
                records = [str(answer).strip('"') for answer in answers]
            else:
                records = [answer.to_text() for answer in answers]

            return {
                "domain": domain,
                "type": record_type,
                "records": records,
            }
        except DNSException as e:
            return {
                "domain": domain,
                "type": record_type,
                "error": f"DNS error: {str(e)}",
            }
        except Exception as e:
            return {
                "domain": domain,
                "type": record_type,
                "error": f"Unexpected error: {str(e)}",
            }

    async def _perform_concurrent_lookups(
        self,
        resolver: dns.asyncresolver.Resolver,
        domain: str,
        record_types: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Perform multiple DNS lookups concurrently for a single domain

        Args:
            resolver: DNS resolver instance
            domain: Domain name to query
            record_types: List of DNS record types

        Returns:
            List of lookup results
        """
        tasks = []
        for record_type in record_types:
            task = self._perform_single_lookup(resolver, domain, record_type)
            tasks.append(task)

        return await asyncio.gather(*tasks)

    async def run(
        self,
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute DNS lookup with given parameters

        Args:
            params: Dictionary of query parameters

        Yields:
            Dictionary containing DNS records or errors
        """
        if not params or "domain" not in params:
            yield {"type": "error", "data": {"message": "Domain parameter is required"}}
            return

        # Parse parameters
        domains_param = params["domain"]
        targets = [d.strip() for d in domains_param.split(",") if d.strip()]

        lookup_mode = params.get("lookup_mode", "forward")

        record_types_param = params.get("record_types", "A")
        record_types = [
            rt.strip().upper() for rt in record_types_param.split(",") if rt.strip()
        ]

        timeout = params.get("timeout", 5.0)

        # Configure resolver
        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout * 2

        # Set custom nameservers if provided
        if "nameservers" in params and params["nameservers"]:
            nameservers = [
                ns.strip() for ns in params["nameservers"].split(",") if ns.strip()
            ]
            resolver.nameservers = nameservers

        # Process targets based on lookup mode
        for target in targets:
            if lookup_mode == "reverse":
                # Validate that target is an IP address for reverse lookup
                if not self._is_ip_address(target):
                    yield {
                        "type": "error",
                        "data": {
                            "message": f"'{target}' is not a valid IP address for reverse lookup"
                        },
                    }
                    continue

                # Handle IP address - perform reverse DNS lookup
                result = await self._perform_reverse_lookup(resolver, target)

                yield {
                    "type": "data",
                    "data": {
                        "target": target,
                        "target_type": "ip_address",
                        "results": [result],
                        "timestamp": time.time(),
                    },
                }
            else:
                # Forward lookup mode - validate that target is not an IP
                if self._is_ip_address(target):
                    yield {
                        "type": "error",
                        "data": {
                            "message": f"'{target}' appears to be an IP address. Use reverse lookup mode for IP addresses."
                        },
                    }
                    continue

                # Handle domain - perform forward DNS lookup
                # Perform concurrent lookups for all record types
                results = await self._perform_concurrent_lookups(
                    resolver, target, record_types
                )

                yield {
                    "type": "data",
                    "data": {
                        "target": target,
                        "target_type": "domain",
                        "results": results,
                        "timestamp": time.time(),
                    },
                }

    def _extract_unique_ips_from_results(self) -> list[dict]:
        """Extract unique IP addresses with metadata from collected DNS results"""
        ip_data_map = {}  # Use dict to avoid duplicates while preserving rich data

        # Get the original query from current params
        original_query = (
            self._current_params.get("domain", "") if self._current_params else ""
        )

        for result in self._evidence_results:
            # result is already the "data" part from the yield
            results = result.get("results", [])
            target = result.get("target", "")
            target_type = result.get("target_type", "")

            # Process each DNS result
            for dns_result in results:
                records = dns_result.get("records", [])
                record_type = dns_result.get("type", "")

                # Extract IP addresses from A and AAAA records
                if record_type in ["A", "AAAA"]:
                    for record in records:
                        if self._is_ip_address(record):
                            # Skip if we already have this IP with better data
                            if record in ip_data_map:
                                continue

                            # Generate description based on DNS lookup context
                            description = self._generate_ip_description(
                                record, f"{target} ({record_type} record)"
                            )

                            ip_data_map[record] = {
                                "ip": record,
                                "description": description,
                            }

        return list(ip_data_map.values())
