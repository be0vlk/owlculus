"""
Enrich person and company data using People Data Labs API

Key features include:
- Dual-mode enrichment supporting both person and company intelligence gathering
- Multi-criteria search using email, phone, name, LinkedIn, and other identifiers
- Comprehensive profile data extraction including employment history and education records
- Company intelligence with employee counts, technology stacks, and industry classifications
- Custom evidence formatting with confidence scoring and API credit usage tracking
"""

from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlmodel import Session

from .base_plugin import BasePlugin


class PeopledatalabsPlugin(BasePlugin):
    """Enrich person and company data using People Data Labs API"""

    def __init__(self, db_session: Session = None):
        super().__init__(display_name="People Data Labs", db_session=db_session)
        self.description = "Enrich person and company data using People Data Labs API"
        self.category = "Person"  # Person, Network, Company, Other
        self.evidence_category = "Associates"  # Social Media, Associates, Network Assets, Communications, Documents, Other
        self.save_to_case = False  # Whether to auto-save results as evidence
        self.api_key_requirements = ["peopledatalabs"]  # Required API key providers
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
            # Note: save_to_case parameter is automatically added by BasePlugin
        }

    def parse_output(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse command output - only needed for subprocess-based plugins"""
        # For direct API/library calls, return None
        return None

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
        if not params or "search_type" not in params:
            yield {
                "type": "error",
                "data": {"message": "Search type parameter is required"},
            }
            return

        # Check API key requirements
        if not self.db_session:
            yield {
                "type": "error",
                "data": {"message": "Database session not available"},
            }
            return

        api_key_status = self.check_api_key_requirements(self.db_session)
        missing_keys = [
            provider
            for provider, configured in api_key_status.items()
            if not configured
        ]
        if missing_keys:
            yield {
                "type": "error",
                "data": {
                    "message": f"API key required for: {', '.join(missing_keys)}. "
                    "Please add it in Admin → Configuration → API Keys"
                },
            }
            return

        search_type = params["search_type"]

        try:
            # Import People Data Labs client
            from app.services.system_config_service import SystemConfigService
            from peopledatalabs import PDLPY

            # Get API key from system configuration
            config_service = SystemConfigService(self.db_session)
            api_key = config_service.get_api_key("peopledatalabs")

            if not api_key:
                yield {
                    "type": "error",
                    "data": {"message": "People Data Labs API key not configured"},
                }
                return

            # Initialize PDL client
            client = PDLPY(api_key=api_key)

            if search_type == "person":
                async for result in self._search_person(client, params):
                    yield result
            elif search_type == "company":
                async for result in self._search_company(client, params):
                    yield result
            else:
                yield {
                    "type": "error",
                    "data": {
                        "message": "Invalid search type. Must be 'person' or 'company'"
                    },
                }

        except ImportError:
            yield {
                "type": "error",
                "data": {
                    "message": "People Data Labs library not installed. Please install 'peopledatalabs' package."
                },
            }
        except Exception as e:
            yield {
                "type": "error",
                "data": {
                    "message": f"Error initializing People Data Labs client: {str(e)}"
                },
            }

    async def _search_person(
        self, client, params: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Search for person data using People Data Labs API"""
        # Build search parameters
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
            yield {
                "type": "error",
                "data": {
                    "message": "At least one person identifier is required (email, phone, name, company, location, or LinkedIn)"
                },
            }
            return

        try:
            # Make API call
            result = client.person.enrichment(**search_params, pretty=True)

            if result.ok:
                person_data = result.json()
                if person_data.get("status") == 200 and person_data.get("data"):
                    yield {
                        "type": "data",
                        "data": {
                            "search_type": "person",
                            "person": person_data["data"],
                            "api_credits_used": person_data.get("credits_used", 1),
                            "confidence": person_data["data"].get(
                                "likelihood", "unknown"
                            ),
                        },
                    }
                else:
                    yield {
                        "type": "error",
                        "data": {
                            "message": "No person data found for the provided criteria"
                        },
                    }
            else:
                error_data = result.json() if result.text else {}
                error_msg = error_data.get("error", {}).get(
                    "message", f"API error: {result.status_code}"
                )
                yield {
                    "type": "error",
                    "data": {"message": f"People Data Labs API error: {error_msg}"},
                }

        except Exception as e:
            yield {
                "type": "error",
                "data": {"message": f"Error searching person data: {str(e)}"},
            }

    async def _search_company(
        self, client, params: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Search for company data using People Data Labs API"""
        # Build search parameters
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
            yield {
                "type": "error",
                "data": {
                    "message": "At least one company identifier is required (name, website, domain, or LinkedIn)"
                },
            }
            return

        try:
            # Make API call
            result = client.company.enrichment(**search_params, pretty=True)

            if result.ok:
                company_data = result.json()
                if company_data.get("status") == 200 and company_data.get("data"):
                    yield {
                        "type": "data",
                        "data": {
                            "search_type": "company",
                            "company": company_data["data"],
                            "api_credits_used": company_data.get("credits_used", 1),
                            "confidence": company_data["data"].get(
                                "likelihood", "unknown"
                            ),
                        },
                    }
                else:
                    yield {
                        "type": "error",
                        "data": {
                            "message": "No company data found for the provided criteria"
                        },
                    }
            else:
                error_data = result.json() if result.text else {}
                error_msg = error_data.get("error", {}).get(
                    "message", f"API error: {result.status_code}"
                )
                yield {
                    "type": "error",
                    "data": {"message": f"People Data Labs API error: {error_msg}"},
                }

        except Exception as e:
            yield {
                "type": "error",
                "data": {"message": f"Error searching company data: {str(e)}"},
            }

    def _format_evidence_content(
        self, results: List[Dict[str, Any]], params: Dict[str, Any]
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

                # Add education if available
                if person.get("education"):
                    content_lines.append("  Education:")
                    for edu in person["education"][:3]:  # Limit to first 3
                        school = edu.get("school", {})
                        content_lines.append(
                            f"    - {school.get('name', 'Unknown')} ({edu.get('start_date', 'N/A')} - {edu.get('end_date', 'N/A')})"
                        )
                    content_lines.append("")

                # Add work experience if available
                if person.get("experience"):
                    content_lines.append("  Work Experience:")
                    for exp in person["experience"][:3]:  # Limit to first 3
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

                # Add technologies if available
                if company.get("technologies"):
                    content_lines.append("  Technologies:")
                    for tech in company["technologies"][:10]:  # Limit to first 10
                        content_lines.append(f"    - {tech.get('name', 'Unknown')}")
                    content_lines.append("")

        return "\n".join(content_lines)
