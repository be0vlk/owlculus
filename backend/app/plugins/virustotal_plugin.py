"""
Analyze files, URLs, domains, and IPs using VirusTotal threat intelligence
"""

import asyncio
import ipaddress
import re
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

import vt
from app.core.dependencies import get_db
from app.services.system_config_service import SystemConfigService
from sqlmodel import Session

from .base_plugin import BasePlugin


class VirustotalPlugin(BasePlugin):
    """Analyze files, URLs, domains, and IPs using VirusTotal threat intelligence"""

    def __init__(self, db_session: Session = None):
        super().__init__(display_name="VirusTotal", db_session=db_session)
        self.description = (
            "Analyze files, URLs, domains, and IPs using VirusTotal threat intelligence"
        )
        self.category = "Other"  # Person, Network, Company, Other
        self.evidence_category = "Other"  # Social Media, Associates, Network Assets, Communications, Documents, Other
        self.save_to_case = False  # Whether to auto-save results as evidence
        self.api_key_requirements = ["virustotal"]  # Required API key providers
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
            # Note: save_to_case parameter is automatically added by BasePlugin
        }

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse command output - only needed for subprocess-based plugins"""
        # For direct API/library calls, return None
        return None

    def _detect_target_type(self, target: str) -> str:
        """Auto-detect the type of target (file hash, URL, domain, or IP)"""
        # Remove whitespace
        target = target.strip()

        # Check if it's a hash (MD5: 32 chars, SHA1: 40 chars, SHA256: 64 chars)
        if re.match(r"^[a-fA-F0-9]{32}$", target):
            return "file"  # MD5
        elif re.match(r"^[a-fA-F0-9]{40}$", target):
            return "file"  # SHA1
        elif re.match(r"^[a-fA-F0-9]{64}$", target):
            return "file"  # SHA256

        # Check if it's a URL
        if target.startswith(("http://", "https://", "ftp://")):
            return "url"

        # Check if it's an IP address
        try:
            ipaddress.ip_address(target)
            return "ip"
        except ValueError:
            pass

        # Check if it looks like a domain (contains dots but no slashes)
        if "." in target and "/" not in target and " " not in target:
            # Basic domain validation
            domain_pattern = r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
            if re.match(domain_pattern, target):
                return "domain"

        # Default to unknown
        return "unknown"

    def _format_detection_ratio(self, stats: Dict[str, int]) -> str:
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

    def _calculate_verdict(self, stats: Dict[str, int]) -> str:
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
        self, params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Main plugin execution method

        Args:
            params: User-provided parameters

        Yields:
            Structured data results
        """
        if not params or "target" not in params:
            yield {"type": "error", "data": {"message": "Target parameter is required"}}
            return

        # Extract parameters
        target = params["target"].strip()
        analysis_type = params.get("analysis_type", "auto")
        include_details = params.get("include_details", True)
        timeout = params.get("timeout", 30.0)

        # Get database session
        db = next(get_db())

        # Check API key requirements
        if hasattr(self, "api_key_requirements") and self.api_key_requirements:
            missing_keys = self.get_missing_api_keys(db)
            if missing_keys:
                yield {
                    "type": "error",
                    "data": {
                        "message": f"API key{'s' if len(missing_keys) > 1 else ''} required for: {', '.join(missing_keys)}. "
                        "Please add them in Admin → Configuration → API Keys"
                    },
                }
                db.close()
                return

        try:
            # Retrieve API key
            config_service = SystemConfigService(db)
            api_key = config_service.get_api_key("virustotal")

            if not api_key:
                yield {
                    "type": "error",
                    "data": {
                        "message": "VirusTotal API key not configured. Please add it in Admin → Configuration → API Keys"
                    },
                }
                return

            # Auto-detect target type if needed
            if analysis_type == "auto":
                detected_type = self._detect_target_type(target)
                if detected_type == "unknown":
                    yield {
                        "type": "error",
                        "data": {
                            "message": f"Could not auto-detect target type for '{target}'. Please specify analysis_type parameter."
                        },
                    }
                    return
                analysis_type = detected_type

            # Initialize VirusTotal client
            async with vt.Client(api_key) as client:
                try:
                    # Set timeout
                    client.timeout = timeout

                    # Perform analysis based on type
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
                        yield {
                            "type": "error",
                            "data": {
                                "message": f"Invalid analysis type: {analysis_type}"
                            },
                        }
                        return

                except vt.error.APIError as e:
                    yield {
                        "type": "error",
                        "data": {"message": f"VirusTotal API error: {str(e)}"},
                    }
                except asyncio.TimeoutError:
                    yield {
                        "type": "error",
                        "data": {
                            "message": f"Request timed out after {timeout} seconds"
                        },
                    }
                except Exception as e:
                    yield {
                        "type": "error",
                        "data": {"message": f"Unexpected error: {str(e)}"},
                    }

        finally:
            db.close()

    async def _analyze_file(
        self, client: vt.Client, file_hash: str, include_details: bool
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Analyze a file hash"""
        file_obj = await client.get_object_async(f"/files/{file_hash}")

        # Basic results
        result = {
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
            # Add vendor detections
            detections = []
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

            # Add tags if available
            if hasattr(file_obj, "tags"):
                result["tags"] = list(file_obj.tags)

        yield {"type": "data", "data": result}

    async def _analyze_url(
        self, client: vt.Client, url: str, include_details: bool
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Analyze a URL"""
        # Generate URL ID
        url_id = vt.url_id(url)
        url_obj = await client.get_object_async(f"/urls/{url_id}")

        # Basic results
        result = {
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
            # Add vendor detections
            detections = []
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

            # Add categories if available
            if hasattr(url_obj, "categories"):
                result["categories"] = dict(url_obj.categories)

        yield {"type": "data", "data": result}

    async def _analyze_domain(
        self, client: vt.Client, domain: str, include_details: bool
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Analyze a domain"""
        domain_obj = await client.get_object_async(f"/domains/{domain}")

        # Basic results
        result = {
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
            # Add vendor detections
            detections = []
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

            # Add categories if available
            if hasattr(domain_obj, "categories"):
                result["categories"] = dict(domain_obj.categories)

        yield {"type": "data", "data": result}

    async def _analyze_ip(
        self, client: vt.Client, ip: str, include_details: bool
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Analyze an IP address"""
        ip_obj = await client.get_object_async(f"/ip_addresses/{ip}")

        # Basic results
        result = {
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
            # Add vendor detections
            detections = []
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

        yield {"type": "data", "data": result}

    def _format_evidence_content(
        self, results: List[Dict[str, Any]], params: Dict[str, Any]
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

        for result in results:
            data = result.get("data", {})

            # Add verdict summary
            content_lines.extend(
                [
                    f"Verdict: {data.get('verdict', 'Unknown')}",
                    f"Detection Ratio: {data.get('detection_ratio', 'N/A')}",
                    f"Last Analysis: {data.get('last_analysis_date', 'Unknown')}",
                    "",
                ]
            )

            # Add target-specific information
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

            # Add detections if available
            detections = data.get("detections", [])
            if detections:
                content_lines.extend(
                    [
                        "Vendor Detections:",
                        "-" * 50,
                    ]
                )
                for detection in detections[:20]:  # Limit to first 20
                    content_lines.append(
                        f"  {detection['vendor']:<20} | {detection['result']:<30} | {detection.get('category', 'Unknown')}"
                    )
                if len(detections) > 20:
                    content_lines.append(
                        f"  ... and {len(detections) - 20} more detections"
                    )
                content_lines.append("")

            # Add categories if available
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

            # Add tags if available
            tags = data.get("tags", [])
            if tags:
                content_lines.extend(
                    [
                        "Tags:",
                        f"  {', '.join(tags[:20])}",
                        "",
                    ]
                )

        return "\n".join(content_lines)
