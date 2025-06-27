"""
Domain investigation hunt definition
"""

from typing import List

from ..base_hunt import BaseHunt, HuntStepDefinition


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
            }
        }

    def get_steps(self) -> List[HuntStepDefinition]:
        return [
            HuntStepDefinition(
                step_id="whois_lookup",
                plugin_name="WhoisPlugin",
                display_name="WHOIS lookup",
                description="Get domain registration information",
                parameter_mapping={"domain": "initial.domain"},
            ),
            HuntStepDefinition(
                step_id="dns_records",
                plugin_name="DnsLookup",
                display_name="DNS records lookup",
                description="Retrieve all DNS records for the domain",
                parameter_mapping={"domain": "initial.domain"},
            ),
            HuntStepDefinition(
                step_id="subdomain_enum",
                plugin_name="SubdomainEnumPlugin",
                display_name="Subdomain enumeration",
                description="Find subdomains of the target domain",
                parameter_mapping={"domain": "initial.domain"},
                timeout_seconds=600,
                optional=True,
            ),
            # This step would use IPs discovered from DNS lookup
            # Demonstrating data passing between steps
            HuntStepDefinition(
                step_id="ip_investigation",
                plugin_name="ShodanPlugin",
                display_name="Investigate discovered IPs",
                description="Analyze IP addresses found in DNS records",
                parameter_mapping={
                    # This would need custom logic to extract IPs from dns_records output
                    "query": "dns_records.results[0].ip_address"
                },
                static_parameters={"search_type": "ip", "limit": 5.0},
                depends_on=["dns_records"],
                optional=True,
            ),
        ]
