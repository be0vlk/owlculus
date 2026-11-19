"""
Enumerate subdomains via Certificate Transparency logs, HackerTarget, and SecurityTrails with DNS verification
"""

from collections.abc import AsyncGenerator, Awaitable, Callable
from functools import partial
from typing import Any

import dns.asyncresolver
import httpx

from app.services.api_key_vault import Provider

from .base_plugin import BasePlugin, PluginRun, ResultEvent
from .plugin_types import DomainSubdomainsWrite, EntityWrite, unique_ip_writes


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
            # Unread since DNS checks run sequentially; kept so plugin
            # metadata and the domain hunt's input stay unchanged.
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

    async def fetch_from_crt(self, client: httpx.AsyncClient, domain: str) -> set[str]:
        """Query crt.sh Certificate Transparency logs for the domain."""
        try:
            resp = await client.get(f"https://crt.sh/?q=%25.{domain}&output=json")
            subdomains = set()
            for entry in resp.json():
                for name in entry.get("name_value", "").split("\n"):
                    name = name.strip().lower()
                    if name.endswith(domain) and "*" not in name:
                        subdomains.add(name)
            return subdomains
        except Exception:
            return set()

    async def fetch_from_hackertarget(
        self, client: httpx.AsyncClient, domain: str
    ) -> set[str]:
        """Query hackertarget.com hostsearch API for the domain."""
        try:
            resp = await client.get(
                f"https://api.hackertarget.com/hostsearch/?q={domain}"
            )
            subdomains = set()
            for line in resp.text.splitlines():
                parts = line.split(",")
                if parts and parts[0].endswith(domain):
                    subdomains.add(parts[0].strip().lower())
            return subdomains
        except Exception:
            return set()

    async def fetch_from_securitytrails(
        self, client: httpx.AsyncClient, domain: str, api_key: str
    ) -> set[str]:
        """Query SecurityTrails API for subdomains of the domain."""
        try:
            resp = await client.get(
                f"https://api.securitytrails.com/v1/domain/{domain}/subdomains",
                headers={"APIKEY": api_key},
            )
            if resp.status_code != 200:
                return set()
            return {
                f"{sub}.{domain}".lower() for sub in resp.json().get("subdomains", [])
            }
        except Exception:
            return set()

    async def resolve_subdomain(self, resolver, fqdn: str) -> dict[str, Any] | None:
        """Resolve a subdomain and return its IP address if found."""
        try:
            ips = [rdata.to_text() for rdata in await resolver.resolve(fqdn, "A")]
        except Exception:
            return None
        return {"subdomain": fqdn, "ip": ips[0] if ips else None, "resolved": True}

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        if not params or "domain" not in params:
            yield self.error("Domain parameter is required")
            return
        domain = params["domain"].lower().strip()
        sources: dict[str, Callable[..., Awaitable[set[str]]]] = {
            "crt.sh": self.fetch_from_crt,
            "HackerTarget": self.fetch_from_hackertarget,
        }
        if params.get("use_securitytrails", False):
            securitytrails_key = ctx.key(Provider.SECURITYTRAILS)
            if not securitytrails_key:
                yield ctx.missing_key(Provider.SECURITYTRAILS)
                return
            sources["SecurityTrails"] = partial(
                self.fetch_from_securitytrails, api_key=securitytrails_key
            )
        subdomain_sources: dict[str, list[str]] = {}
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for source, fetch in sources.items():
                for sub in await fetch(client, domain):
                    subdomain_sources.setdefault(sub, []).append(source)
        if not subdomain_sources:
            yield self.data({"status": "No subdomains found", "phase": "complete"})
            return
        resolver = dns.asyncresolver.Resolver()
        resolved_count = 0
        for subdomain in sorted(subdomain_sources):
            result = await self.resolve_subdomain(resolver, subdomain) or {
                "subdomain": subdomain,
                "ip": None,
                "resolved": False,
            }
            resolved_count += result["resolved"]
            result["source"] = ", ".join(subdomain_sources[subdomain])
            yield self.data(result)
        yield self.data(
            {
                "status": "complete",
                "phase": "summary",
                "total_discovered": len(subdomain_sources),
                "total_resolved": resolved_count,
                "sources_used": list(sources),
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
            "",
        ]
        discovered_subdomains = [
            data for data in results if "subdomain" in data and "ip" in data
        ]
        summary = next(
            (data for data in results if data.get("phase") == "summary"), None
        )
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
                    f"{sub.get('subdomain', 'Unknown'):<50} → {sub.get('ip') or 'N/A':<15} (Source: {sub.get('source', 'Unknown')})"
                )
        return "\n".join(content_lines)

    def entity_writes(self, payloads, params):
        """Describe the IP and parent-domain writes for collected findings."""
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
