"""
Analyze files, URLs, domains, and IPs using VirusTotal threat intelligence
"""

import re
import time
import urllib.parse
from collections.abc import AsyncGenerator
from typing import Any

import vt

from app.services.api_key_vault import Provider

from .base_plugin import BasePlugin, PluginRun, ResultEvent
from .plugin_types import is_ip_address

_ENDPOINTS = {
    "file": "/files/",
    "url": "/urls/",
    "domain": "/domains/",
    "ip": "/ip_addresses/",
}


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
        if is_ip_address(target):
            return "ip"
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

    def _format_date(self, dt_obj: Any, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """Format a datetime object or timestamp to string"""
        if hasattr(dt_obj, "strftime"):
            return dt_obj.strftime(fmt)
        elif isinstance(dt_obj, (int, float)):
            return time.strftime(fmt, time.localtime(dt_obj))
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
        if analysis_type == "auto":
            analysis_type = self._detect_target_type(target)
            if analysis_type == "unknown":
                yield self.error(
                    f"Could not auto-detect target type for '{target}'. Please specify analysis_type parameter."
                )
                return
        if analysis_type not in _ENDPOINTS:
            yield self.error(f"Invalid analysis type: {analysis_type}")
            return
        # Quoting leaves ".." intact and the HTTP client collapses it into the parent path.
        if analysis_type != "url" and target == "..":
            yield self.error(f"Invalid target: '{target}'")
            return
        try:
            async with vt.Client(api_key) as client:
                client.timeout = timeout
                result = await self._analyze(
                    client, analysis_type, target, include_details
                )
        except vt.error.APIError as e:
            yield self.error(f"VirusTotal API error: {e!s}")
        except TimeoutError:
            yield self.error(f"Request timed out after {timeout} seconds")
        except Exception as e:
            yield self.error(f"Unexpected error: {e!s}")
        else:
            yield self.data(result)

    async def _analyze(
        self, client: vt.Client, kind: str, target: str, include_details: bool
    ) -> dict[str, Any]:
        """Look up one file hash, URL, domain or IP and shape the report."""
        object_id = (
            vt.url_id(target) if kind == "url" else urllib.parse.quote(target, safe="")
        )
        obj = await client.get_object_async(_ENDPOINTS[kind] + object_id)
        stats = obj.last_analysis_stats
        result: dict[str, Any] = {
            "target": target,
            "target_type": "ip_address" if kind == "ip" else kind,
            "detection_ratio": self._format_detection_ratio(stats),
            "verdict": self._calculate_verdict(stats),
            "last_analysis_date": self._format_date(obj.last_analysis_date),
            f"{kind}_info": self._info(kind, obj, target),
        }
        if include_details:
            # Files list every vendor with any result; other kinds skip "clean".
            result["detections"] = sorted(
                (
                    {
                        "vendor": vendor,
                        "result": analysis["result"],
                        "category": analysis.get("category", "Unknown"),
                    }
                    for vendor, analysis in obj.last_analysis_results.items()
                    if (
                        analysis["result"]
                        if kind == "file"
                        else analysis["result"] != "clean"
                    )
                ),
                key=lambda detection: detection["vendor"],
            )
            if kind == "file" and obj.get("tags") is not None:
                result["tags"] = list(obj.tags)
            if kind in {"url", "domain"} and obj.get("categories") is not None:
                result["categories"] = dict(obj.categories)
        return result

    def _info(self, kind: str, obj: vt.Object, target: str) -> dict[str, Any]:
        if kind == "file":
            return {
                "sha256": obj.sha256,
                "sha1": obj.sha1,
                "md5": obj.md5,
                "size": obj.size,
                "type": obj.type_description,
                "names": list(obj.get("names", [])),
            }
        if kind == "url":
            return {
                "final_url": obj.get("last_final_url", target),
                "title": obj.get("title"),
            }
        if kind == "domain":
            # Attribute access converts VirusTotal timestamps to UTC datetimes.
            created = getattr(obj, "creation_date", None)
            return {
                "reputation": obj.get("reputation", 0),
                "registrar": obj.get("registrar"),
                "creation_date": (
                    None if created is None else self._format_date(created, "%Y-%m-%d")
                ),
            }
        return {
            "asn": obj.get("asn"),
            "as_owner": obj.get("as_owner"),
            "country": obj.get("country"),
            "reputation": obj.get("reputation", 0),
        }

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
