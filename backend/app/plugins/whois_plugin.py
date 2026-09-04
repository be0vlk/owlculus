"""
Query domain Whois information using python-whois library
"""

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import whois

from .base_plugin import BasePlugin, PluginRun, ResultEvent


class WhoisPlugin(BasePlugin):
    """Query domain Whois information"""

    def __init__(self):
        super().__init__(display_name="Whois Lookup")
        self.description = "Query domain registration and ownership information"
        self.category = "Network"
        self.evidence_category = "Network Assets"
        self.parameters = {
            "domain": {
                "type": "string",
                "description": "Domain name to query (e.g., example.com)",
                "required": True,
            },
            "timeout": {
                "type": "float",
                "description": "Query timeout in seconds",
                "default": 30.0,
                "required": False,
            },
        }

    def _format_date(self, date_value) -> str | None:
        """Format date value for display"""
        if not date_value:
            return None
        if isinstance(date_value, list):
            date_value = date_value[0] if date_value else None
        if isinstance(date_value, datetime):
            return date_value.strftime("%Y-%m-%d %H:%M:%S UTC")
        elif isinstance(date_value, str):
            return date_value
        else:
            return str(date_value) if date_value else None

    def _format_list_field(self, field_value) -> list[str]:
        """Format list field for display"""
        if not field_value:
            return []
        if isinstance(field_value, list):
            return [str(item).strip() for item in field_value if item]
        else:
            return [str(field_value).strip()]

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
        domain = params["domain"].strip().lower()
        timeout = params.get("timeout", 30.0)
        if domain.startswith(("http://", "https://")):
            domain = domain.split("://", 1)[1]
        if "/" in domain:
            domain = domain.split("/", 1)[0]
        if not domain:
            yield self.error("Invalid domain format")
            return
        try:
            loop = asyncio.get_event_loop()
            whois_data = await asyncio.wait_for(
                loop.run_in_executor(None, whois.whois, domain), timeout=timeout
            )
            if not whois_data:
                yield self.error(f"No whois data found for {domain}")
                return
            result_data = {
                "domain": domain,
                "registrar": getattr(whois_data, "registrar", None),
                "creation_date": self._format_date(
                    getattr(whois_data, "creation_date", None)
                ),
                "expiration_date": self._format_date(
                    getattr(whois_data, "expiration_date", None)
                ),
                "updated_date": self._format_date(
                    getattr(whois_data, "updated_date", None)
                ),
                "name_servers": self._format_list_field(
                    getattr(whois_data, "name_servers", [])
                ),
                "status": self._format_list_field(getattr(whois_data, "status", [])),
                "emails": self._format_list_field(getattr(whois_data, "emails", [])),
                "org": getattr(whois_data, "org", None),
                "registrant_name": getattr(whois_data, "name", None),
                "registrant_country": getattr(whois_data, "country", None),
                "admin_email": getattr(whois_data, "admin_email", None),
                "tech_email": getattr(whois_data, "tech_email", None),
                "whois_server": getattr(whois_data, "whois_server", None),
                "dnssec": getattr(whois_data, "dnssec", None),
            }
            cleaned_data = {
                k: v for k, v in result_data.items() if v is not None and v != []
            }
            if cleaned_data.get("creation_date"):
                try:
                    creation = getattr(whois_data, "creation_date", None)
                    if isinstance(creation, list):
                        creation = creation[0]
                    if isinstance(creation, datetime):
                        age_days = (datetime.now() - creation).days
                        cleaned_data["domain_age_days"] = age_days
                        cleaned_data["domain_age_years"] = round(age_days / 365.25, 1)
                except:
                    pass
            if cleaned_data.get("expiration_date"):
                try:
                    expiration = getattr(whois_data, "expiration_date", None)
                    if isinstance(expiration, list):
                        expiration = expiration[0]
                    if isinstance(expiration, datetime):
                        days_until_exp = (expiration - datetime.now()).days
                        cleaned_data["days_until_expiration"] = days_until_exp
                        if days_until_exp < 30:
                            cleaned_data["expiration_warning"] = (
                                f"Domain expires in {days_until_exp} days"
                            )
                except:
                    pass
            yield self.data(cleaned_data)
        except TimeoutError:
            yield self.error(f"Whois query timed out for {domain}")
        except Exception as e:
            error_msg = str(e)
            if "No whois server" in error_msg or "not found" in error_msg.lower():
                yield self.error(f"Domain {domain} not found or invalid TLD")
            else:
                yield self.error(f"Whois query failed: {error_msg}")

    def format_evidence(
        self, results: list[dict[str, Any]], params: dict[str, Any]
    ) -> str:
        """Custom formatting for whois evidence content"""
        if not results:
            return f"Whois Lookup Results\n{'=' * 50}\n\nNo results found."
        content_lines = [
            "Whois Lookup Results",
            "=" * 50,
            "",
            f"Domain: {params.get('domain', 'Unknown')}",
            f"Query time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
        ]
        for result in results:
            if "domain" in result:
                content_lines.extend(["Registration Information:", "-" * 30])
                if result.get("registrar"):
                    content_lines.append(f"Registrar: {result['registrar']}")
                if result.get("org"):
                    content_lines.append(f"Organization: {result['org']}")
                if result.get("registrant_name"):
                    content_lines.append(f"Registrant: {result['registrant_name']}")
                if result.get("registrant_country"):
                    content_lines.append(f"Country: {result['registrant_country']}")
                content_lines.append("")
                content_lines.extend(["Important Dates:", "-" * 30])
                if result.get("creation_date"):
                    content_lines.append(f"Created: {result['creation_date']}")
                if result.get("updated_date"):
                    content_lines.append(f"Updated: {result['updated_date']}")
                if result.get("expiration_date"):
                    content_lines.append(f"Expires: {result['expiration_date']}")
                if result.get("domain_age_years"):
                    content_lines.append(
                        f"Domain Age: {result['domain_age_years']} years"
                    )
                if result.get("days_until_expiration"):
                    content_lines.append(
                        f"Days until expiration: {result['days_until_expiration']}"
                    )
                content_lines.append("")
                if result.get("name_servers"):
                    content_lines.extend(["Name Servers:", "-" * 30])
                    for ns in result["name_servers"]:
                        content_lines.append(f"  {ns}")
                    content_lines.append("")
                if result.get("status"):
                    content_lines.extend(["Status:", "-" * 30])
                    for status in result["status"]:
                        content_lines.append(f"  {status}")
                    content_lines.append("")
                if result.get("emails"):
                    content_lines.extend(["Contact Emails:", "-" * 30])
                    for email in result["emails"]:
                        content_lines.append(f"  {email}")
                    content_lines.append("")
                if result.get("expiration_warning"):
                    content_lines.extend(
                        [
                            "⚠️  WARNINGS:",
                            "-" * 30,
                            f"  {result['expiration_warning']}",
                            "",
                        ]
                    )
        return "\n".join(content_lines)
