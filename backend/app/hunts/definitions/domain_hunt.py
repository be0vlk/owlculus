"""
Domain investigation hunt definition
"""

from ..base_hunt import BaseHunt, HuntStepDefinition
from ..step_input_resolver import HuntInputExpression, parse_input_expression


class DomainHunt(BaseHunt):
    """Comprehensive domain and infrastructure investigation"""

    def __init__(self):
        super().__init__()
        self.display_name = "Domain Investigation"
        self.description = "Comprehensive analysis of a domain including WHOIS, DNS, subdomains, and associated infrastructure"
        self.category = "domain"

        self.initial_parameters = {
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
            "use_securitytrails": {
                "type": "boolean",
                "description": "Enable SecurityTrails API for enhanced subdomain discovery",
                "default": False,
                "required": False,
            },
        }

    def get_steps(self) -> list[HuntStepDefinition]:
        subdomain_param_mapping: dict[str, HuntInputExpression] = {
            "domain": parse_input_expression("initial.domain"),
            "concurrency": parse_input_expression("initial.subdomain_concurrency"),
            "use_securitytrails": parse_input_expression("initial.use_securitytrails"),
        }

        return [
            HuntStepDefinition(
                step_id="whois_lookup",
                plugin_name="WhoisPlugin",
                display_name="WHOIS lookup",
                description="Get domain registration information",
                parameter_mapping={"domain": parse_input_expression("initial.domain")},
                optional=True,
            ),
            HuntStepDefinition(
                step_id="dns_records",
                plugin_name="DnsLookup",
                display_name="DNS records lookup",
                description="Retrieve all DNS records for the domain",
                parameter_mapping={"domain": parse_input_expression("initial.domain")},
            ),
            HuntStepDefinition(
                step_id="subdomain_enum",
                plugin_name="SubdomainEnumPlugin",
                display_name="Subdomain enumeration",
                description="Find subdomains of the target domain",
                parameter_mapping=subdomain_param_mapping,
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
                    "query": parse_input_expression(
                        "dns_records.results[0].results[0].records[0]"
                    )
                },
                static_parameters={"search_type": "ip", "limit": 10.0},
                depends_on=["dns_records"],
                optional=True,
            ),
            # Note: IPs discovered from subdomain enumeration are automatically
            # processed by SubdomainEnumPlugin and saved as IP entities.
            # For detailed investigation of those IPs, run individual Shodan
            # queries manually from the case management interface.
        ]
