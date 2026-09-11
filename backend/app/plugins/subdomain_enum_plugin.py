"""
Enumerate subdomains via Certificate Transparency logs, HackerTarget, and SecurityTrails with DNS verification
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

import aiohttp
import dns.asyncresolver

from app.services.api_key_vault import Provider

from .base_plugin import BasePlugin, PluginRun, ResultEvent
from .plugin_types import EntityWrite

_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


class SubdomainEnumPlugin(BasePlugin):
    """Enumerate subdomains via Certificate Transparency logs, HackerTarget, and SecurityTrails with DNS verification"""

    def __init__(self):
        super().__init__(display_name="Subdomain Enumeration")
        self.description = "Enumerate subdomains via Certificate Transparency logs, HackerTarget, and SecurityTrails with DNS verification"
        self.category = "Network"
        self.evidence_category = "Network Assets"
        self.parameters = {
            "domain": {
                "type": "string",
                "description": "Target base domain (e.g., example.com)",
                "required": True,
            },
            "concurrency": {
                "type": "float",
                "description": "Maximum concurrent DNS queries",
                "default": 5.0,
                "required": False,
            },
            "use_securitytrails": {
                "type": "boolean",
                "description": "Enable SecurityTrails API (requires API key)",
                "default": False,
                "required": False,
            },
        }

    async def fetch_from_crt(self, domain: str) -> set[str]:
        """Query crt.sh Certificate Transparency logs for the domain."""
        query = f"%25.{domain}"
        url = f"https://crt.sh/?q={query}&output=json"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=_REQUEST_TIMEOUT) as resp:
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

    async def fetch_from_hackertarget(self, domain: str) -> set[str]:
        """Query hackertarget.com hostsearch API for the domain."""
        url = f"https://api.hackertarget.com/hostsearch/?q={domain}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=_REQUEST_TIMEOUT) as resp:
                    text = await resp.text()
            subdomains = set()
            for line in text.splitlines():
                parts = line.split(",")
                if parts and parts[0].endswith(domain):
                    subdomains.add(parts[0].strip().lower())
            return subdomains
        except Exception:
            return set()

    async def fetch_from_securitytrails(self, domain: str, api_key: str) -> set[str]:
        """Query SecurityTrails API for subdomains of the domain."""
        if not api_key:
            return set()
        url = f"https://api.securitytrails.com/v1/domain/{domain}/subdomains"
        headers = {"APIKEY": api_key}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=_REQUEST_TIMEOUT) as resp:
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
    ) -> dict[str, Any] | None:
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

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        """
        Main plugin execution method

        Args:
            params: User-provided parameters

        Yields:
            Structured data results
        """
        if not params or "domain" not in params:
            yield self.error("Domain parameter is required")
            return
        domain = params["domain"].lower().strip()
        concurrency = int(params.get("concurrency", 50))
        use_securitytrails = params.get("use_securitytrails", False)
        securitytrails_key = None
        if use_securitytrails:
            securitytrails_key = ctx.key(Provider.SECURITYTRAILS)
            if not securitytrails_key:
                yield ctx.missing_key(Provider.SECURITYTRAILS)
                return
        crt_subs = await self.fetch_from_crt(domain)
        ht_subs = await self.fetch_from_hackertarget(domain)
        st_subs = set()
        if use_securitytrails and securitytrails_key:
            st_subs = await self.fetch_from_securitytrails(domain, securitytrails_key)
        all_subdomains = crt_subs.union(ht_subs).union(st_subs)
        if not all_subdomains:
            yield self.data({"status": "No subdomains found", "phase": "complete"})
            return
        resolver = dns.asyncresolver.Resolver()
        semaphore = asyncio.Semaphore(concurrency)
        subdomain_sources: dict[str, list[str]] = {}
        for sub in crt_subs:
            subdomain_sources.setdefault(sub, []).append("crt.sh")
        for sub in ht_subs:
            subdomain_sources.setdefault(sub, []).append("HackerTarget")
        for sub in st_subs:
            subdomain_sources.setdefault(sub, []).append("SecurityTrails")
        tasks = []
        for subdomain in sorted(all_subdomains):
            task = self.resolve_subdomain(resolver, semaphore, subdomain)
            tasks.append((subdomain, task))
        resolved_count = 0
        for subdomain, task in tasks:
            result = await task
            if result:
                resolved_count += 1
                result["source"] = ", ".join(
                    subdomain_sources.get(subdomain, ["Unknown"])
                )
                yield self.data(result)
            else:
                yield self.data(
                    {
                        "subdomain": subdomain,
                        "ip": None,
                        "resolved": False,
                        "source": ", ".join(
                            subdomain_sources.get(subdomain, ["Unknown"])
                        ),
                    }
                )
        yield self.data(
            {
                "status": "complete",
                "phase": "summary",
                "total_discovered": len(all_subdomains),
                "total_resolved": resolved_count,
                "sources_used": ["crt.sh", "HackerTarget"]
                + (["SecurityTrails"] if use_securitytrails else []),
            }
        )

    def format_evidence(
        self, results: list[dict[str, Any]], params: dict[str, Any]
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
        discovered_subdomains = []
        status_messages = []
        summary = None
        for data in results:
            if "subdomain" in data and "ip" in data:
                discovered_subdomains.append(data)
            elif data.get("phase") == "summary":
                summary = data
            elif "status" in data:
                status_messages.append(data.get("status", ""))
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
        if discovered_subdomains:
            content_lines.extend(["Resolved Subdomains:", "-" * 20])
            discovered_subdomains.sort(key=lambda x: x.get("subdomain", ""))
            for sub in discovered_subdomains:
                content_lines.append(
                    f"{sub.get('subdomain', 'Unknown'):<50} → {sub.get('ip', 'N/A'):<15} (Source: {sub.get('source', 'Unknown')})"
                )
        return "\n".join(content_lines)

    def entity_writes(self, payloads, params):
        """Describe the IP and parent-domain writes for collected findings."""
        from .base_plugin import unique_ip_writes
        from .plugin_types import DomainSubdomainsWrite

        ip_candidates = []
        subdomain_list = []
        base_domain = params.get("domain", "").lower().strip()
        for result in payloads:
            if "subdomain" in result:
                subdomain_info = {
                    "subdomain": result.get("subdomain", ""),
                    "ip": result.get("ip"),
                    "resolved": result.get("resolved", False),
                    "source": result.get("source", "Unknown"),
                }
                if (
                    subdomain_info["subdomain"]
                    and subdomain_info["subdomain"] != base_domain
                ):
                    subdomain_list.append(subdomain_info)
                ip = result.get("ip")
                if result.get("resolved"):
                    ip_candidates.append(
                        (
                            ip,
                            result.get("subdomain", ""),
                            {"ip_address": result.get("source", "Unknown")},
                        )
                    )
        writes: list[EntityWrite] = list(unique_ip_writes(ip_candidates))
        if base_domain and subdomain_list:
            writes.append(DomainSubdomainsWrite(base_domain, subdomain_list))
        return writes
