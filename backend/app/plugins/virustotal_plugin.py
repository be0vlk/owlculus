"""
Analyze files, URLs, domains, and IPs using VirusTotal threat intelligence
"""

import ipaddress
import re
import time
from collections.abc import AsyncGenerator
from typing import Any

import vt

from app.services.api_key_vault import Provider

from .base_plugin import BasePlugin, PluginRun, ResultEvent


class VirustotalPlugin(BasePlugin):
    """Analyze files, URLs, domains, and IPs using VirusTotal threat intelligence"""

    def __init__(self):
        super().__init__(display_name="VirusTotal")
        self.description = (
            "Analyze files, URLs, domains, and IPs using VirusTotal threat intelligence"
        )
        self.category = "Other"
        self.evidence_category = "Other"
        self.api_key_requirements = [Provider.VIRUSTOTAL]
        self.parameters = {
            "target": {
                "type": "string",
                "description": "File hash (MD5/SHA1/SHA256), URL, domain, or IP address to analyze",
                "required": True,
            },
            "analysis_type": {
                "type": "string",
                "description": "Type of analysis: auto, file, url, domain, ip (default: auto-detect)",
                "default": "auto",
                "required": False,
            },
            "include_details": {
                "type": "boolean",
                "description": "Include extended analysis details (vendors, metadata, etc.)",
                "default": True,
                "required": False,
            },
            "timeout": {
                "type": "float",
                "description": "API timeout in seconds",
                "default": 30.0,
                "required": False,
            },
        }

    def _detect_target_type(self, target: str) -> str:
        """Auto-detect the type of target (file hash, URL, domain, or IP)"""
        target = target.strip()
        if (
            re.match("^[a-fA-F0-9]{32}$", target)
            or re.match("^[a-fA-F0-9]{40}$", target)
            or re.match("^[a-fA-F0-9]{64}$", target)
        ):
            return "file"
        if target.startswith(("http://", "https://", "ftp://")):
            return "url"
        try:
            ipaddress.ip_address(target)
            return "ip"
        except ValueError:
            pass
        if "." in target and "/" not in target and (" " not in target):
            domain_pattern = "^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
            if re.match(domain_pattern, target):
                return "domain"
        return "unknown"

    def _format_detection_ratio(self, stats: dict[str, int]) -> str:
        """Format detection statistics into a readable ratio"""
        malicious = stats.get("malicious", 0)
        total = sum(stats.values()) - stats.get("unsupported", 0)
        return f"{malicious}/{total}"

    def _format_datetime(self, dt_obj: Any) -> str:
        """Format a datetime object or timestamp to string"""
        if hasattr(dt_obj, "strftime"):
            return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(dt_obj, (int, float)):
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(dt_obj))
        else:
            return str(dt_obj)

    def _format_date(self, dt_obj: Any) -> str:
        """Format a date object or timestamp to string (date only)"""
        if hasattr(dt_obj, "strftime"):
            return dt_obj.strftime("%Y-%m-%d")
        elif isinstance(dt_obj, (int, float)):
            return time.strftime("%Y-%m-%d", time.localtime(dt_obj))
        else:
            return str(dt_obj)

    def _calculate_verdict(self, stats: dict[str, int]) -> str:
        """Calculate overall verdict based on detection stats"""
        malicious = stats.get("malicious", 0)
        suspicious = stats.get("suspicious", 0)
        total = sum(stats.values()) - stats.get("unsupported", 0)
        if total == 0:
            return "Unknown"
        threat_score = (malicious * 2 + suspicious) / (total * 2)
        if threat_score == 0:
            return "Clean"
        elif threat_score < 0.1:
            return "Likely Safe"
        elif threat_score < 0.3:
            return "Suspicious"
        elif threat_score < 0.5:
            return "Likely Malicious"
        else:
            return "Malicious"

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
        if not params or "target" not in params:
            yield self.error("Target parameter is required")
            return
        target = params["target"].strip()
        analysis_type = params.get("analysis_type", "auto")
        include_details = params.get("include_details", True)
        timeout = params.get("timeout", 30.0)
        api_key = ctx.key(Provider.VIRUSTOTAL)
        if not api_key:
            yield ctx.missing_key(Provider.VIRUSTOTAL)
            return
        try:
            if analysis_type == "auto":
                detected_type = self._detect_target_type(target)
                if detected_type == "unknown":
                    yield self.error(
                        f"Could not auto-detect target type for '{target}'. Please specify analysis_type parameter."
                    )
                    return
                analysis_type = detected_type
            async with vt.Client(api_key) as client:
                try:
                    client.timeout = timeout
                    if analysis_type == "file":
                        async for result in self._analyze_file(
                            client, target, include_details
                        ):
                            yield result
                    elif analysis_type == "url":
                        async for result in self._analyze_url(
                            client, target, include_details
                        ):
                            yield result
                    elif analysis_type == "domain":
                        async for result in self._analyze_domain(
                            client, target, include_details
                        ):
                            yield result
                    elif analysis_type == "ip":
                        async for result in self._analyze_ip(
                            client, target, include_details
                        ):
                            yield result
                    else:
                        yield self.error(f"Invalid analysis type: {analysis_type}")
                        return
                except vt.error.APIError as e:
                    yield self.error(f"VirusTotal API error: {e!s}")
                except TimeoutError:
                    yield self.error(f"Request timed out after {timeout} seconds")
                except Exception as e:
                    yield self.error(f"Unexpected error: {e!s}")
        except Exception as error:
            yield self.error(f"Unexpected error: {error!s}")

    async def _analyze_file(
        self, client: vt.Client, file_hash: str, include_details: bool
    ) -> AsyncGenerator[ResultEvent, None]:
        """Analyze a file hash"""
        file_obj = await client.get_object_async(f"/files/{file_hash}")
        result: dict[str, Any] = {
            "target": file_hash,
            "target_type": "file",
            "detection_ratio": self._format_detection_ratio(
                file_obj.last_analysis_stats
            ),
            "verdict": self._calculate_verdict(file_obj.last_analysis_stats),
            "last_analysis_date": self._format_datetime(file_obj.last_analysis_date),
            "file_info": {
                "sha256": file_obj.sha256,
                "sha1": file_obj.sha1,
                "md5": file_obj.md5,
                "size": file_obj.size,
                "type": file_obj.type_description,
                "names": list(file_obj.names) if hasattr(file_obj, "names") else [],
            },
        }
        if include_details:
            detections: list[dict[str, Any]] = []
            for vendor, analysis in file_obj.last_analysis_results.items():
                if analysis["result"]:
                    detections.append(
                        {
                            "vendor": vendor,
                            "result": analysis["result"],
                            "category": analysis.get("category", "Unknown"),
                        }
                    )
            result["detections"] = sorted(detections, key=lambda x: x["vendor"])
            if hasattr(file_obj, "tags"):
                result["tags"] = list(file_obj.tags)
        yield self.data(result)

    async def _analyze_url(
        self, client: vt.Client, url: str, include_details: bool
    ) -> AsyncGenerator[ResultEvent, None]:
        """Analyze a URL"""
        url_id = vt.url_id(url)
        url_obj = await client.get_object_async(f"/urls/{url_id}")
        result: dict[str, Any] = {
            "target": url,
            "target_type": "url",
            "detection_ratio": self._format_detection_ratio(
                url_obj.last_analysis_stats
            ),
            "verdict": self._calculate_verdict(url_obj.last_analysis_stats),
            "last_analysis_date": self._format_datetime(url_obj.last_analysis_date),
            "url_info": {
                "final_url": (
                    url_obj.last_final_url
                    if hasattr(url_obj, "last_final_url")
                    else url
                ),
                "title": url_obj.title if hasattr(url_obj, "title") else None,
            },
        }
        if include_details:
            detections: list[dict[str, Any]] = []
            for vendor, analysis in url_obj.last_analysis_results.items():
                if analysis["result"] != "clean":
                    detections.append(
                        {
                            "vendor": vendor,
                            "result": analysis["result"],
                            "category": analysis.get("category", "Unknown"),
                        }
                    )
            result["detections"] = sorted(detections, key=lambda x: x["vendor"])
            if hasattr(url_obj, "categories"):
                result["categories"] = dict(url_obj.categories)
        yield self.data(result)

    async def _analyze_domain(
        self, client: vt.Client, domain: str, include_details: bool
    ) -> AsyncGenerator[ResultEvent, None]:
        """Analyze a domain"""
        domain_obj = await client.get_object_async(f"/domains/{domain}")
        result: dict[str, Any] = {
            "target": domain,
            "target_type": "domain",
            "detection_ratio": self._format_detection_ratio(
                domain_obj.last_analysis_stats
            ),
            "verdict": self._calculate_verdict(domain_obj.last_analysis_stats),
            "last_analysis_date": self._format_datetime(domain_obj.last_analysis_date),
            "domain_info": {
                "reputation": (
                    domain_obj.reputation if hasattr(domain_obj, "reputation") else 0
                ),
                "registrar": (
                    domain_obj.registrar if hasattr(domain_obj, "registrar") else None
                ),
                "creation_date": (
                    self._format_date(domain_obj.creation_date)
                    if hasattr(domain_obj, "creation_date")
                    else None
                ),
            },
        }
        if include_details:
            detections: list[dict[str, Any]] = []
            for vendor, analysis in domain_obj.last_analysis_results.items():
                if analysis["result"] != "clean":
                    detections.append(
                        {
                            "vendor": vendor,
                            "result": analysis["result"],
                            "category": analysis.get("category", "Unknown"),
                        }
                    )
            result["detections"] = sorted(detections, key=lambda x: x["vendor"])
            if hasattr(domain_obj, "categories"):
                result["categories"] = dict(domain_obj.categories)
        yield self.data(result)

    async def _analyze_ip(
        self, client: vt.Client, ip: str, include_details: bool
    ) -> AsyncGenerator[ResultEvent, None]:
        """Analyze an IP address"""
        ip_obj = await client.get_object_async(f"/ip_addresses/{ip}")
        result: dict[str, Any] = {
            "target": ip,
            "target_type": "ip_address",
            "detection_ratio": self._format_detection_ratio(ip_obj.last_analysis_stats),
            "verdict": self._calculate_verdict(ip_obj.last_analysis_stats),
            "last_analysis_date": self._format_datetime(ip_obj.last_analysis_date),
            "ip_info": {
                "asn": ip_obj.asn if hasattr(ip_obj, "asn") else None,
                "as_owner": ip_obj.as_owner if hasattr(ip_obj, "as_owner") else None,
                "country": ip_obj.country if hasattr(ip_obj, "country") else None,
                "reputation": ip_obj.reputation if hasattr(ip_obj, "reputation") else 0,
            },
        }
        if include_details:
            detections: list[dict[str, Any]] = []
            for vendor, analysis in ip_obj.last_analysis_results.items():
                if analysis["result"] != "clean":
                    detections.append(
                        {
                            "vendor": vendor,
                            "result": analysis["result"],
                            "category": analysis.get("category", "Unknown"),
                        }
                    )
            result["detections"] = sorted(detections, key=lambda x: x["vendor"])
        yield self.data(result)

    def format_evidence(
        self, results: list[dict[str, Any]], params: dict[str, Any]
    ) -> str:
        """Custom formatting for evidence content"""
        content_lines = [
            f"{self.display_name} Analysis Report",
            "=" * 70,
            "",
            f"Analysis Date: {time.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Target: {params.get('target', 'Unknown')}",
            f"Analysis Type: {params.get('analysis_type', 'auto-detected')}",
            "",
        ]
        for data in results:
            content_lines.extend(
                [
                    f"Verdict: {data.get('verdict', 'Unknown')}",
                    f"Detection Ratio: {data.get('detection_ratio', 'N/A')}",
                    f"Last Analysis: {data.get('last_analysis_date', 'Unknown')}",
                    "",
                ]
            )
            target_type = data.get("target_type", "")
            if target_type == "file":
                file_info = data.get("file_info", {})
                content_lines.extend(
                    [
                        "File Information:",
                        f"  SHA256: {file_info.get('sha256', 'N/A')}",
                        f"  SHA1: {file_info.get('sha1', 'N/A')}",
                        f"  MD5: {file_info.get('md5', 'N/A')}",
                        f"  Size: {file_info.get('size', 'N/A')} bytes",
                        f"  Type: {file_info.get('type', 'N/A')}",
                        "",
                    ]
                )
                if file_info.get("names"):
                    content_lines.extend(
                        [
                            "Known Filenames:",
                            *[f"  - {name}" for name in file_info["names"][:10]],
                            "",
                        ]
                    )
            elif target_type == "url":
                url_info = data.get("url_info", {})
                content_lines.extend(
                    [
                        "URL Information:",
                        f"  Final URL: {url_info.get('final_url', 'N/A')}",
                        f"  Title: {url_info.get('title', 'N/A')}",
                        "",
                    ]
                )
            elif target_type == "domain":
                domain_info = data.get("domain_info", {})
                content_lines.extend(
                    [
                        "Domain Information:",
                        f"  Registrar: {domain_info.get('registrar', 'N/A')}",
                        f"  Creation Date: {domain_info.get('creation_date', 'N/A')}",
                        f"  Reputation: {domain_info.get('reputation', 'N/A')}",
                        "",
                    ]
                )
            elif target_type == "ip_address":
                ip_info = data.get("ip_info", {})
                content_lines.extend(
                    [
                        "IP Information:",
                        f"  ASN: {ip_info.get('asn', 'N/A')}",
                        f"  AS Owner: {ip_info.get('as_owner', 'N/A')}",
                        f"  Country: {ip_info.get('country', 'N/A')}",
                        f"  Reputation: {ip_info.get('reputation', 'N/A')}",
                        "",
                    ]
                )
            detections = data.get("detections", [])
            if detections:
                content_lines.extend(["Vendor Detections:", "-" * 50])
                for detection in detections[:20]:
                    content_lines.append(
                        f"  {detection['vendor']:<20} | {detection['result']:<30} | {detection.get('category', 'Unknown')}"
                    )
                if len(detections) > 20:
                    content_lines.append(
                        f"  ... and {len(detections) - 20} more detections"
                    )
                content_lines.append("")
            categories = data.get("categories", {})
            if categories:
                content_lines.extend(
                    [
                        "Categories:",
                        *[
                            f"  - {vendor}: {category}"
                            for vendor, category in list(categories.items())[:10]
                        ],
                        "",
                    ]
                )
            tags = data.get("tags", [])
            if tags:
                content_lines.extend(["Tags:", f"  {', '.join(tags[:20])}", ""])
        return "\n".join(content_lines)
