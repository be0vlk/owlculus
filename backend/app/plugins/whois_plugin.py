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
            whois_data = await asyncio.wait_for(
                asyncio.to_thread(whois.whois, domain), timeout=timeout
            )
            if not whois_data:
                yield self.error(f"No whois data found for {domain}")
                return
            creation = _first(getattr(whois_data, "creation_date", None))
            expiration = _first(getattr(whois_data, "expiration_date", None))
            result_data = {
                "domain": domain,
                "registrar": getattr(whois_data, "registrar", None),
                "creation_date": _format_date(creation),
                "expiration_date": _format_date(expiration),
                "updated_date": _format_date(
                    _first(getattr(whois_data, "updated_date", None))
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
            if isinstance(creation, datetime):
                age_days = (datetime.now(creation.tzinfo) - creation).days
                cleaned_data["domain_age_days"] = age_days
                cleaned_data["domain_age_years"] = round(age_days / 365.25, 1)
            if isinstance(expiration, datetime):
                days_until_exp = (expiration - datetime.now(expiration.tzinfo)).days
                cleaned_data["days_until_expiration"] = days_until_exp
                if days_until_exp < 30:
                    cleaned_data["expiration_warning"] = (
                        f"Domain expires in {days_until_exp} days"
                    )
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
            if "domain" not in result:
                continue
            for heading, lines in _EVIDENCE_FIELDS:
                content_lines.extend([heading, "-" * 30])
                content_lines.extend(
                    line.format(result[key]) for line, key in lines if result.get(key)
                )
                content_lines.append("")
            for heading, key in _EVIDENCE_LISTS:
                if result.get(key):
                    content_lines.extend([heading, "-" * 30])
                    content_lines.extend(f"  {item}" for item in result[key])
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


_EVIDENCE_FIELDS = (
    (
        "Registration Information:",
        (
            ("Registrar: {}", "registrar"),
            ("Organization: {}", "org"),
            ("Registrant: {}", "registrant_name"),
            ("Country: {}", "registrant_country"),
        ),
    ),
    (
        "Important Dates:",
        (
            ("Created: {}", "creation_date"),
            ("Updated: {}", "updated_date"),
            ("Expires: {}", "expiration_date"),
            ("Domain Age: {} years", "domain_age_years"),
            ("Days until expiration: {}", "days_until_expiration"),
        ),
    ),
)
_EVIDENCE_LISTS = (
    ("Name Servers:", "name_servers"),
    ("Status:", "status"),
    ("Contact Emails:", "emails"),
)


def _first(value):
    """Whois returns one value or a list of values for repeated fields."""
    return value[0] if isinstance(value, list) and value else value


def _format_date(value) -> str | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S UTC")
    return str(value)
