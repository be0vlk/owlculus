"""
Domain investigation hunt definition
"""

from typing import List, Optional

from sqlmodel import Session

from ..base_hunt import BaseHunt, HuntStepDefinition


class DomainHunt(BaseHunt):
    """Comprehensive domain and infrastructure investigation"""

    def __init__(self, db_session: Optional[Session] = None):
        super().__init__()
        self.display_name = "Domain Investigation"
        self.description = "Comprehensive analysis of a domain including WHOIS, DNS, subdomains, and associated infrastructure"
        self.category = "domain"

        # Build parameters dynamically based on API key availability
        self.initial_parameters = self._build_parameters(db_session)

    def _build_parameters(self, db_session: Optional[Session] = None) -> dict:
        """Build parameters dynamically based on available API keys"""
        base_parameters = {
            "domain": {
                "type": "string",
                "description": "Domain name to investigate (e.g., example.com)",
                "required": True,
            },
            "subdomain_concurrency": {
                "type": "float",
                "description": "Maximum concurrent DNS queries for subdomain enumeration",
                "default": 10.0,
                "required": False,
            },
        }

        # Only add SecurityTrails parameter if API key is configured
        if self._is_securitytrails_available(db_session):
            base_parameters["use_securitytrails"] = {
                "type": "boolean",
                "description": "Enable SecurityTrails API for enhanced subdomain discovery",
                "default": False,
                "required": False,
            }

        return base_parameters

    def _is_securitytrails_available(
        self, db_session: Optional[Session] = None
    ) -> bool:
        """Check if SecurityTrails API key is configured"""
        if not db_session:
            return False

        try:
            from app.services.system_config_service import SystemConfigService

            config_service = SystemConfigService(db_session)
            return config_service.is_provider_configured("securitytrails")
        except Exception:
            # If we can't check, assume it's not available
            return False

    def get_steps(self) -> List[HuntStepDefinition]:
        # Build subdomain enumeration parameter mapping based on available parameters
        subdomain_param_mapping = {
            "domain": "initial.domain",
            "concurrency": "initial.subdomain_concurrency",
        }

        # Only add SecurityTrails mapping if the parameter exists
        if "use_securitytrails" in self.initial_parameters:
            subdomain_param_mapping["use_securitytrails"] = "initial.use_securitytrails"

        return [
            HuntStepDefinition(
                step_id="whois_lookup",
                plugin_name="WhoisPlugin",
                display_name="WHOIS lookup",
                description="Get domain registration information",
                parameter_mapping={"domain": "initial.domain"},
                timeout_seconds=120,
                optional=True,
            ),
            HuntStepDefinition(
                step_id="dns_records",
                plugin_name="DnsLookup",
                display_name="DNS records lookup",
                description="Retrieve all DNS records for the domain",
                parameter_mapping={"domain": "initial.domain"},
                timeout_seconds=180,
            ),
            HuntStepDefinition(
                step_id="subdomain_enum",
                plugin_name="SubdomainEnumPlugin",
                display_name="Subdomain enumeration",
                description="Find subdomains of the target domain",
                parameter_mapping=subdomain_param_mapping,
                timeout_seconds=600,
                optional=True,
            ),
            # Investigate the main domain's IP address
            HuntStepDefinition(
                step_id="ip_investigation_from_dns",
                plugin_name="ShodanPlugin",
                display_name="Investigate main domain IP",
                description="Analyze the IP address of the main domain using Shodan",
                parameter_mapping={
                    # Extract first A record IP from DNS lookup results
                    "query": "dns_records.results[0].results[0].records[0]"
                },
                static_parameters={"search_type": "ip", "limit": 10.0},
                depends_on=["dns_records"],
                timeout_seconds=90,
                optional=True,
            ),
            # Note: IPs discovered from subdomain enumeration are automatically
            # processed by SubdomainEnumPlugin and saved as IP entities.
            # For detailed investigation of those IPs, run individual Shodan
            # queries manually from the case management interface.
        ]
