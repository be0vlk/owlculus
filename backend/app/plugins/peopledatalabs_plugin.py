"""
Enrich person and company data using People Data Labs API
"""

from collections.abc import AsyncGenerator
from typing import Any

from app.services.api_key_vault import Provider

from .base_plugin import BasePlugin, PluginRun, ResultEvent


class PeopledatalabsPlugin(BasePlugin):
    """Enrich person and company data using People Data Labs API"""

    def __init__(self):
        super().__init__(display_name="People Data Labs")
        self.description = "Enrich person and company data using People Data Labs API"
        self.category = "Person"
        self.evidence_category = "Associates"
        self.api_key_requirements = [Provider.PEOPLE_DATA_LABS]
        self.parameters = {
            "search_type": {
                "type": "string",
                "description": "Type of search to perform",
                "required": True,
                "options": ["person", "company"],
            },
            "email": {
                "type": "string",
                "description": "Email address (person search)",
                "required": False,
            },
            "phone": {
                "type": "string",
                "description": "Phone number (person search)",
                "required": False,
            },
            "name": {
                "type": "string",
                "description": "Full name (person search) or company name",
                "required": False,
            },
            "company": {
                "type": "string",
                "description": "Company name (person search)",
                "required": False,
            },
            "website": {
                "type": "string",
                "description": "Company website (company search)",
                "required": False,
            },
            "domain": {
                "type": "string",
                "description": "Company domain (company search)",
                "required": False,
            },
            "location": {
                "type": "string",
                "description": "Location (person search)",
                "required": False,
            },
            "linkedin": {
                "type": "string",
                "description": "LinkedIn profile URL",
                "required": False,
            },
        }

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
        if not params or "search_type" not in params:
            yield self.error("Search type parameter is required")
            return
        search_type = params["search_type"]
        api_key = ctx.key(Provider.PEOPLE_DATA_LABS)
        if not api_key:
            yield ctx.missing_key(Provider.PEOPLE_DATA_LABS)
            return
        try:
            from peopledatalabs import PDLPY

            client = PDLPY(api_key=api_key)
            if search_type == "person":
                async for result in self._search_person(client, params):
                    yield result
            elif search_type == "company":
                async for result in self._search_company(client, params):
                    yield result
            else:
                yield self.error("Invalid search type. Must be 'person' or 'company'")
        except ImportError:
            yield self.error(
                "People Data Labs library not installed. Please install 'peopledatalabs' package."
            )
        except Exception as e:
            yield self.error(f"Error initializing People Data Labs client: {e!s}")

    async def _search_person(
        self, client, params: dict[str, Any]
    ) -> AsyncGenerator[ResultEvent, None]:
        """Search for person data using People Data Labs API"""
        search_params = {}
        if params.get("email"):
            search_params["email"] = params["email"]
        if params.get("phone"):
            search_params["phone"] = params["phone"]
        if params.get("name"):
            search_params["name"] = params["name"]
        if params.get("company"):
            search_params["company"] = params["company"]
        if params.get("location"):
            search_params["location"] = params["location"]
        if params.get("linkedin"):
            search_params["profile"] = params["linkedin"]
        if not search_params:
            yield self.error(
                "At least one person identifier is required (email, phone, name, company, location, or LinkedIn)"
            )
            return
        try:
            result = client.person.enrichment(**search_params, pretty=True)
            if result.ok:
                person_data = result.json()
                if person_data.get("status") == 200 and person_data.get("data"):
                    yield self.data(
                        {
                            "search_type": "person",
                            "person": person_data["data"],
                            "api_credits_used": person_data.get("credits_used", 1),
                            "confidence": person_data["data"].get(
                                "likelihood", "unknown"
                            ),
                        }
                    )
                else:
                    yield self.error("No person data found for the provided criteria")
            else:
                error_data = result.json() if result.text else {}
                error_msg = error_data.get("error", {}).get(
                    "message", f"API error: {result.status_code}"
                )
                yield self.error(f"People Data Labs API error: {error_msg}")
        except Exception as e:
            yield self.error(f"Error searching person data: {e!s}")

    async def _search_company(
        self, client, params: dict[str, Any]
    ) -> AsyncGenerator[ResultEvent, None]:
        """Search for company data using People Data Labs API"""
        search_params = {}
        if params.get("name"):
            search_params["name"] = params["name"]
        if params.get("website"):
            search_params["website"] = params["website"]
        if params.get("domain"):
            search_params["website"] = params["domain"]
        if params.get("linkedin"):
            search_params["profile"] = params["linkedin"]
        if not search_params:
            yield self.error(
                "At least one company identifier is required (name, website, domain, or LinkedIn)"
            )
            return
        try:
            result = client.company.enrichment(**search_params, pretty=True)
            if result.ok:
                company_data = result.json()
                if company_data.get("status") == 200 and company_data.get("data"):
                    yield self.data(
                        {
                            "search_type": "company",
                            "company": company_data["data"],
                            "api_credits_used": company_data.get("credits_used", 1),
                            "confidence": company_data["data"].get(
                                "likelihood", "unknown"
                            ),
                        }
                    )
                else:
                    yield self.error("No company data found for the provided criteria")
            else:
                error_data = result.json() if result.text else {}
                error_msg = error_data.get("error", {}).get(
                    "message", f"API error: {result.status_code}"
                )
                yield self.error(f"People Data Labs API error: {error_msg}")
        except Exception as e:
            yield self.error(f"Error searching company data: {e!s}")

    def format_evidence(
        self, results: list[dict[str, Any]], params: dict[str, Any]
    ) -> str:
        """Custom formatting for evidence content"""
        content_lines = [
            f"{self.display_name} Investigation Results",
            "=" * 50,
            "",
            f"Search Type: {params.get('search_type', 'Unknown')}",
            f"Total results: {len(results)}",
            "",
        ]
        for i, result in enumerate(results, 1):
            if result.get("search_type") == "person" and result.get("person"):
                person = result["person"]
                content_lines.extend(
                    [
                        f"Person Result #{i}:",
                        f"  Full Name: {person.get('full_name', 'N/A')}",
                        f"  First Name: {person.get('first_name', 'N/A')}",
                        f"  Last Name: {person.get('last_name', 'N/A')}",
                        f"  Email: {', '.join(person.get('emails', []) or ['N/A'])}",
                        f"  Phone: {', '.join(person.get('phone_numbers', []) or ['N/A'])}",
                        f"  Location: {person.get('location_name', 'N/A')}",
                        f"  Job Title: {person.get('job_title', 'N/A')}",
                        f"  Company: {person.get('job_company_name', 'N/A')}",
                        f"  Industry: {person.get('job_title_role', 'N/A')}",
                        f"  LinkedIn: {person.get('linkedin_url', 'N/A')}",
                        f"  Confidence: {result.get('confidence', 'Unknown')}",
                        f"  API Credits Used: {result.get('api_credits_used', 'N/A')}",
                        "",
                    ]
                )
                if person.get("education"):
                    content_lines.append("  Education:")
                    for edu in person["education"][:3]:
                        school = edu.get("school", {})
                        content_lines.append(
                            f"    - {school.get('name', 'Unknown')} ({edu.get('start_date', 'N/A')} - {edu.get('end_date', 'N/A')})"
                        )
                    content_lines.append("")
                if person.get("experience"):
                    content_lines.append("  Work Experience:")
                    for exp in person["experience"][:3]:
                        company = exp.get("company", {})
                        content_lines.append(
                            f"    - {exp.get('title', 'Unknown')} at {company.get('name', 'Unknown')} ({exp.get('start_date', 'N/A')} - {exp.get('end_date', 'Present')})"
                        )
                    content_lines.append("")
            elif result.get("search_type") == "company" and result.get("company"):
                company = result["company"]
                content_lines.extend(
                    [
                        f"Company Result #{i}:",
                        f"  Name: {company.get('name', 'N/A')}",
                        f"  Website: {company.get('website', 'N/A')}",
                        f"  Domain: {company.get('domain', 'N/A')}",
                        f"  Industry: {company.get('industry', 'N/A')}",
                        f"  Size: {company.get('size', 'N/A')}",
                        f"  Founded: {company.get('founded', 'N/A')}",
                        f"  Location: {company.get('location_name', 'N/A')}",
                        f"  Country: {company.get('location_country', 'N/A')}",
                        f"  LinkedIn: {company.get('linkedin_url', 'N/A')}",
                        f"  Employee Count: {company.get('employee_count', 'N/A')}",
                        f"  Revenue: {company.get('estimated_num_employees', 'N/A')}",
                        f"  Type: {company.get('type', 'N/A')}",
                        f"  Confidence: {result.get('confidence', 'Unknown')}",
                        f"  API Credits Used: {result.get('api_credits_used', 'N/A')}",
                        "",
                    ]
                )
                if company.get("technologies"):
                    content_lines.append("  Technologies:")
                    for tech in company["technologies"][:10]:
                        content_lines.append(f"    - {tech.get('name', 'Unknown')}")
                    content_lines.append("")
        return "\n".join(content_lines)
