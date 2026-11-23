"""
Enrich person and company data using People Data Labs API
"""

import json
import os
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import peopledatalabs

from app.services.api_key_vault import Provider

from .base_plugin import BasePlugin, PluginRun, ResultEvent

_MONID_API = "https://api.monid.ai"
_MONID_TIMEOUT = 60

# (request parameter, People Data Labs field); a later company domain wins.
_FIELDS = {
    "person": (
        ("email", "email"),
        ("phone", "phone"),
        ("name", "name"),
        ("company", "company"),
        ("location", "location"),
        ("linkedin", "profile"),
    ),
    "company": (
        ("name", "name"),
        ("website", "website"),
        ("domain", "website"),
        ("linkedin", "profile"),
    ),
}
_MISSING_IDENTIFIER = {
    "person": "At least one person identifier is required (email, phone, name, company, location, or LinkedIn)",
    "company": "At least one company identifier is required (name, website, domain, or LinkedIn)",
}


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

    def get_metadata(self) -> dict[str, Any]:
        metadata = super().get_metadata()
        if os.environ.get("MONID_API_KEY"):
            metadata["api_key_requirements"] = []
        return metadata

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        if not params or "search_type" not in params:
            yield self.error("Search type parameter is required")
            return
        search_type = params["search_type"]
        if search_type == "person" and (monid_key := os.environ.get("MONID_API_KEY")):
            yield self._enrich(None, search_type, params, monid_key=monid_key)
            return
        api_key = ctx.key(Provider.PEOPLE_DATA_LABS)
        if not api_key:
            yield ctx.missing_key(Provider.PEOPLE_DATA_LABS)
            return
        if search_type not in _FIELDS:
            yield self.error("Invalid search type. Must be 'person' or 'company'")
            return
        try:
            client = peopledatalabs.PDLPY(api_key=api_key)
        except Exception as e:
            yield self.error(f"Error initializing People Data Labs client: {e!s}")
            return
        yield self._enrich(getattr(client, search_type), search_type, params)

    def _enrich(
        self,
        endpoint,
        kind: str,
        params: dict[str, Any],
        *,
        monid_key: str | None = None,
    ) -> ResultEvent:
        """Enrich one person or company from the identifiers given for it."""
        search_params = {
            field: params[param] for param, field in _FIELDS[kind] if params.get(param)
        }
        if not search_params:
            return self.error(_MISSING_IDENTIFIER[kind])
        try:
            if monid_key:
                run = self._run_monid(monid_key, {**search_params, "pretty": True})
                provider_response = run.get("providerResponse") or {}
                status = provider_response.get("httpStatus", 200)
                if status >= 400:
                    error_data = provider_response.get("error")
                    if not isinstance(error_data, dict):
                        error_data = {}
                    return self._provider_error(status, error_data)
                body = run["output"]
            else:
                result = endpoint.enrichment(**search_params, pretty=True)
                if not result.ok:
                    error_data = result.json() if result.text else {}
                    return self._provider_error(result.status_code, error_data)
                body = result.json()
            if body.get("status") != 200 or not body.get("data"):
                return self.error(f"No {kind} data found for the provided criteria")
            return self.data(
                {
                    "search_type": kind,
                    kind: body["data"],
                    "api_credits_used": body.get("credits_used", 1),
                    "confidence": body["data"].get("likelihood", "unknown"),
                }
            )
        except Exception as e:
            return self.error(f"Error searching {kind} data: {e!s}")

    def _provider_error(self, status: int, error_data: dict[str, Any]) -> ResultEvent:
        error_msg = error_data.get("error", {}).get("message", f"API error: {status}")
        return self.error(f"People Data Labs API error: {error_msg}")

    @staticmethod
    def _run_monid(api_key: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "provider": "pdl",
            "endpoint": "/v5/person/enrich",
            "input": {"body": params},
        }
        deadline = time.monotonic() + _MONID_TIMEOUT
        response = httpx.post(
            f"{_MONID_API}/v1/run",
            headers={**headers, "Content-Type": "application/json; charset=utf-8"},
            content=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=_MONID_TIMEOUT,
        )
        response.raise_for_status()
        run = response.json()
        if response.status_code == 202:
            run_id = run["runId"]
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 2:
                    raise TimeoutError("Monid run timed out")
                time.sleep(2)
                response = httpx.get(
                    f"{_MONID_API}/v1/runs/{run_id}",
                    headers=headers,
                    timeout=remaining - 2,
                )
                response.raise_for_status()
                run = response.json()
                if run.get("status") in {
                    "COMPLETED",
                    "FAILED",
                    "TIMED_OUT",
                    "STOPPED",
                    "BLOCKED",
                }:
                    break
        if run.get("status") not in (None, "COMPLETED"):
            raise RuntimeError(f"Monid run {run['status']}")
        return run

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
