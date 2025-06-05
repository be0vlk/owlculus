"""
DNS lookup plugin for resolving domain names to IP addresses
"""

from typing import AsyncGenerator, Dict, Any, Optional, List
import asyncio
import time
from functools import lru_cache
import dns.asyncresolver
from dns.rdatatype import RdataType
from dns.exception import DNSException

from .base_plugin import BasePlugin


class DnsLookup(BasePlugin):
    """DNS lookup plugin for resolving domain names to IP addresses"""

    def __init__(self):
        super().__init__(display_name="DNS Lookup")
        self.description = "Resolves domain names to IP addresses and DNS records"
        self.category = "Network"
        self.save_to_case = False
        self.parameters = {
            "domain": {
                "type": "string",
                "description": "Domain name to resolve (or comma-separated list for bulk lookup)",
                "required": True,
            },
            "record_types": {
                "type": "string",
                "description": "Comma-separated DNS record types (A,AAAA,MX,TXT,NS,CNAME)",
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
            "use_cache": {
                "type": "boolean",
                "description": "Use cached results if available",
                "default": True,
                "required": False,
            },
        }
        # Simple in-memory cache with TTL
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Not used as DNS queries are handled directly"""
        return None

    def _get_cache_key(self, domain: str, record_type: str) -> str:
        """Generate cache key for a domain and record type"""
        return f"{domain.lower()}:{record_type}"

    def _get_cached_result(self, domain: str, record_type: str) -> Optional[List[str]]:
        """Get cached result if available and not expired"""
        cache_key = self._get_cache_key(domain, record_type)
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return cached_data
            else:
                # Expired, remove from cache
                del self._cache[cache_key]
        return None

    def _cache_result(self, domain: str, record_type: str, results: List[str]):
        """Cache DNS query results"""
        cache_key = self._get_cache_key(domain, record_type)
        self._cache[cache_key] = (results, time.time())

    async def _perform_single_lookup(
        self,
        resolver: dns.asyncresolver.Resolver,
        domain: str,
        record_type: str,
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Perform a single DNS lookup for a specific record type
        
        Args:
            resolver: DNS resolver instance
            domain: Domain name to query
            record_type: DNS record type (A, AAAA, MX, etc.)
            use_cache: Whether to use cached results
            
        Returns:
            Dictionary containing query results or error
        """
        # Check cache first
        if use_cache:
            cached = self._get_cached_result(domain, record_type)
            if cached is not None:
                return {
                    "domain": domain,
                    "type": record_type,
                    "records": cached,
                    "cached": True,
                }

        try:
            rdata_type = getattr(RdataType, record_type.upper())
            answers = await resolver.resolve(domain, rdata_type)
            
            # Format results based on record type
            if record_type.upper() == "MX":
                records = [f"{answer.preference} {answer.exchange}" for answer in answers]
            elif record_type.upper() == "TXT":
                records = [str(answer).strip('"') for answer in answers]
            else:
                records = [answer.to_text() for answer in answers]
            
            # Cache the results
            if use_cache:
                self._cache_result(domain, record_type, records)
            
            return {
                "domain": domain,
                "type": record_type,
                "records": records,
                "cached": False,
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
        use_cache: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Perform multiple DNS lookups concurrently for a single domain
        
        Args:
            resolver: DNS resolver instance
            domain: Domain name to query
            record_types: List of DNS record types
            use_cache: Whether to use cached results
            
        Returns:
            List of lookup results
        """
        tasks = []
        for record_type in record_types:
            task = self._perform_single_lookup(resolver, domain, record_type, use_cache)
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
        domains = [d.strip() for d in domains_param.split(",") if d.strip()]
        
        record_types_param = params.get("record_types", "A")
        record_types = [rt.strip().upper() for rt in record_types_param.split(",") if rt.strip()]
        
        timeout = params.get("timeout", 5.0)
        use_cache = params.get("use_cache", True)
        
        # Configure resolver
        resolver = dns.asyncresolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout * 2
        
        # Set custom nameservers if provided
        if "nameservers" in params and params["nameservers"]:
            nameservers = [ns.strip() for ns in params["nameservers"].split(",") if ns.strip()]
            resolver.nameservers = nameservers

        # Process domains
        for domain in domains:
            yield {
                "type": "status",
                "data": {"message": f"Looking up {domain}..."},
            }
            
            # Perform concurrent lookups for all record types
            results = await self._perform_concurrent_lookups(
                resolver, domain, record_types, use_cache
            )
            
            # Yield results for this domain
            yield {
                "type": "data",
                "data": {
                    "domain": domain,
                    "results": results,
                    "timestamp": time.time(),
                },
            }

        # Report cache statistics
        cache_hits = sum(1 for r in self._cache.values() if time.time() - r[1] < self._cache_ttl)
        yield {
            "type": "complete",
            "data": {
                "message": f"DNS lookup completed for {len(domains)} domain(s)",
                "cache_entries": cache_hits,
            },
        }