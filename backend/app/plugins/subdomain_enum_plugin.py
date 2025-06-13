"""
Enumerate subdomains via Certificate Transparency logs, HackerTarget, and SecurityTrails with DNS verification
"""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Set

import aiohttp
import dns.asyncresolver
from sqlmodel import Session

from .base_plugin import BasePlugin


class SubdomainEnumPlugin(BasePlugin):
    """Enumerate subdomains via Certificate Transparency logs, HackerTarget, and SecurityTrails with DNS verification"""

    def __init__(self, db_session: Session = None):
        super().__init__(display_name="Subdomain Enumeration", db_session=db_session)
        self.description = "Enumerate subdomains via Certificate Transparency logs, HackerTarget, and SecurityTrails with DNS verification"
        self.category = "Network"  # Person, Network, Company, Other
        self.evidence_category = "Network Assets"  # Social Media, Associates, Network Assets, Communications, Documents, Other
        self.save_to_case = False  # Whether to auto-save results as evidence
        self.parameters = {
            "domain": {
                "type": "string",
                "description": "Target base domain (e.g., example.com)",
                "required": True,
            },
            "concurrency": {
                "type": "float",
                "description": "Maximum concurrent DNS queries",
                "default": 50.0,
                "required": False,
            },
            "use_securitytrails": {
                "type": "boolean",
                "description": "Enable SecurityTrails API (requires API key)",
                "default": False,
                "required": False,
            },
            # Note: save_to_case parameter is automatically added by BasePlugin
        }

    async def fetch_from_crt(self, domain: str) -> Set[str]:
        """Query crt.sh Certificate Transparency logs for the domain."""
        query = f"%25.{domain}"
        url = f"https://crt.sh/?q={query}&output=json"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    text = await resp.text()

            entries = json.loads(text)
            subdomains = set()

            for entry in entries:
                for name in entry.get("name_value", "").split("\n"):
                    name = name.strip().lower()
                    if name.endswith(domain) and "*" not in name:
                        subdomains.add(name)

            return subdomains
        except Exception:
            return set()

    async def fetch_from_hackertarget(self, domain: str) -> Set[str]:
        """Query hackertarget.com hostsearch API for the domain."""
        url = f"https://api.hackertarget.com/hostsearch/?q={domain}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as resp:
                    text = await resp.text()

            subdomains = set()
            for line in text.splitlines():
                parts = line.split(",")
                if parts and parts[0].endswith(domain):
                    subdomains.add(parts[0].strip().lower())

            return subdomains
        except Exception:
            return set()

    async def fetch_from_securitytrails(self, domain: str, api_key: str) -> Set[str]:
        """Query SecurityTrails API for subdomains of the domain."""
        if not api_key:
            return set()

        url = f"https://api.securitytrails.com/v1/domain/{domain}/subdomains"
        headers = {"APIKEY": api_key}

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=30) as resp:
                    if resp.status != 200:
                        return set()
                    data = await resp.json()

            subdomains = set()
            for sub in data.get("subdomains", []):
                fqdn = f"{sub}.{domain}".lower()
                subdomains.add(fqdn)

            return subdomains
        except Exception:
            return set()

    async def resolve_subdomain(
        self, resolver, semaphore, fqdn: str
    ) -> Optional[Dict[str, Any]]:
        """Resolve a subdomain and return its IP address if found."""
        try:
            async with semaphore:
                answers = await resolver.resolve(fqdn, "A")
            ips = [rdata.to_text() for rdata in answers]
            return {"subdomain": fqdn, "ip": ips[0] if ips else None, "resolved": True}
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.exception.Timeout):
            return None
        except Exception:
            return None

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse command output - only needed for subprocess-based plugins"""
        # For direct API/library calls, return None
        return None

    async def run(
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Main plugin execution method

        Args:
            params: User-provided parameters

        Yields:
            Structured data results
        """
        if not params or "domain" not in params:
            yield {"type": "error", "data": {"message": "Domain parameter is required"}}
            return

        # Extract parameters
        domain = params["domain"].lower().strip()
        concurrency = int(params.get("concurrency", 50))
        use_securitytrails = params.get("use_securitytrails", False)

        # Check for SecurityTrails API key if needed
        securitytrails_key = None
        if use_securitytrails:
            if self.db_session:
                from app.services.system_config_service import SystemConfigService

                config_service = SystemConfigService(self.db_session)
                securitytrails_key = config_service.get_api_key("securitytrails")

                if not securitytrails_key:
                    yield {
                        "type": "error",
                        "data": {
                            "message": "SecurityTrails API key not configured. Please add it in Admin → Configuration → API Keys or disable SecurityTrails option"
                        },
                    }
                    return

        # Fetch subdomains from multiple sources
        crt_subs = await self.fetch_from_crt(domain)
        ht_subs = await self.fetch_from_hackertarget(domain)

        st_subs = set()
        if use_securitytrails and securitytrails_key:
            st_subs = await self.fetch_from_securitytrails(domain, securitytrails_key)

        # Combine all discovered subdomains
        all_subdomains = crt_subs.union(ht_subs).union(st_subs)

        if not all_subdomains:
            yield {
                "type": "data",
                "data": {"status": "No subdomains found", "phase": "complete"},
            }
            return

        # Prepare DNS resolver
        resolver = dns.asyncresolver.Resolver()
        semaphore = asyncio.Semaphore(concurrency)

        # Track sources for each subdomain
        subdomain_sources = {}
        for sub in crt_subs:
            subdomain_sources.setdefault(sub, []).append("crt.sh")
        for sub in ht_subs:
            subdomain_sources.setdefault(sub, []).append("HackerTarget")
        for sub in st_subs:
            subdomain_sources.setdefault(sub, []).append("SecurityTrails")

        # Resolve subdomains

        # Create tasks for DNS resolution
        tasks = []
        for subdomain in sorted(all_subdomains):
            task = self.resolve_subdomain(resolver, semaphore, subdomain)
            tasks.append((subdomain, task))

        # Execute DNS resolutions and yield results as they complete
        resolved_count = 0
        for subdomain, task in tasks:
            result = await task
            if result:
                resolved_count += 1
                result["source"] = ", ".join(
                    subdomain_sources.get(subdomain, ["Unknown"])
                )
                yield {"type": "data", "data": result}
            else:
                # Yield unresolved subdomains too
                yield {
                    "type": "data",
                    "data": {
                        "subdomain": subdomain,
                        "ip": None,
                        "resolved": False,
                        "source": ", ".join(
                            subdomain_sources.get(subdomain, ["Unknown"])
                        ),
                    },
                }

        # Final summary
        yield {
            "type": "data",
            "data": {
                "status": "complete",
                "phase": "summary",
                "total_discovered": len(all_subdomains),
                "total_resolved": resolved_count,
                "sources_used": ["crt.sh", "HackerTarget"]
                + (["SecurityTrails"] if use_securitytrails else []),
            },
        }

        # Evidence saving is handled automatically by BasePlugin
        # No manual implementation needed - just yield data results

    def _format_evidence_content(
        self, results: List[Dict[str, Any]], params: Dict[str, Any]
    ) -> str:
        """Custom formatting for evidence content"""
        content_lines = [
            f"{self.display_name} Investigation Results",
            "=" * 70,
            "",
            f"Target Domain: {params.get('domain', 'Unknown')}",
            f"Execution Time: {params.get('execution_time', 'Unknown')}",
            "",
        ]

        # Separate different types of results
        discovered_subdomains = []
        status_messages = []
        summary = None

        for result in results:
            data = result.get("data", {})
            if "subdomain" in data and "ip" in data:
                discovered_subdomains.append(data)
            elif data.get("phase") == "summary":
                summary = data
            elif "status" in data:
                status_messages.append(data.get("status", ""))

        # Add summary
        if summary:
            content_lines.extend(
                [
                    "Summary:",
                    "-" * 20,
                    f"Total Unique Subdomains Found: {summary.get('total_discovered', 0)}",
                    f"Successfully Resolved: {summary.get('total_resolved', 0)}",
                    f"Sources Used: {', '.join(summary.get('sources_used', []))}",
                    "",
                ]
            )

        # Add resolved subdomains
        if discovered_subdomains:
            content_lines.extend(
                [
                    "Resolved Subdomains:",
                    "-" * 20,
                ]
            )

            # Sort by subdomain name
            discovered_subdomains.sort(key=lambda x: x.get("subdomain", ""))

            for sub in discovered_subdomains:
                content_lines.append(
                    f"{sub.get('subdomain', 'Unknown'):<50} → {sub.get('ip', 'N/A'):<15} (Source: {sub.get('source', 'Unknown')})"
                )

        return "\n".join(content_lines)
