"""Plugin-catalogue adapter for the entity-correlation query."""

from collections.abc import AsyncGenerator
from typing import Any

from app.core.exceptions import BaseException as DomainException
from app.core.utils import get_utc_now
from app.database.models import Case
from app.schemas.entity_schema import entity_display_name
from app.services.entity_correlation import (
    CorrelationKind,
    CorrelationMatch,
    EntityCorrelation,
)

from .base_plugin import BasePlugin, PluginRun, ResultEvent


class CorrelationScan(BasePlugin):
    """Keep cross-case correlation available in the plugin catalogue."""

    def __init__(self):
        super().__init__(display_name="Correlation Scan")
        self.description = "Finds matching entities and relationships across cases"
        self.category = "Other"
        self.evidence_category = "Documents"
        self.parameters = {
            "case_id": {
                "type": "integer",
                "description": "ID of the case to scan",
                "required": True,
            }
        }

    async def run(
        self, params: dict[str, Any], ctx: PluginRun
    ) -> AsyncGenerator[ResultEvent, None]:
        del params
        if ctx.case_id is None:
            yield self.error("Case ID is required")
            return
        case = ctx.session.get(Case, ctx.case_id)
        if case is None:
            yield self.error("Case not found")
            return
        try:
            matches = EntityCorrelation(ctx.session).correlate(case, ctx.user)
        except DomainException as error:
            yield self.error(str(error))
            return
        for payload in _result_payloads(matches, ctx.case_id):
            yield self.data(payload)

    def format_evidence(
        self, results: list[dict[str, Any]], params: dict[str, Any]
    ) -> str:
        """Render browser-shaped correlation payloads as saved evidence."""
        del params
        if not results:
            return ""
        lines = [
            "Correlation Scan Results",
            "=" * 50,
            "",
            f"Total entities with matches: {len(results)}",
            f"Case ID: {results[0]['case_id']}",
            f"Execution time: {get_utc_now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
        ]
        for group in results:
            lines.extend(
                [
                    f"Entity: {group['entity_name']}",
                    f"Type: {group['entity_type']}",
                    f"Match Type: {group['match_type']}",
                    "",
                    "Related Cases and Details:",
                ]
            )
            lines.extend(
                f"Case: {match['case_title']} (#{match['case_number']})"
                for match in group["matches"]
            )
            lines.extend(["", "=" * 50, ""])
        return "\n".join(lines)


def _result_payloads(
    matches: list[CorrelationMatch], case_id: int
) -> list[dict[str, Any]]:
    groups: dict[tuple[int | None, CorrelationKind, str], dict[str, Any]] = {}
    for match in matches:
        key = (match.entity.id, match.kind, match.value.casefold())
        payload = groups.setdefault(key, _group_payload(match, case_id))
        payload["matches"].append(_other_entity_payload(match))
    return list(groups.values())


def _group_payload(match: CorrelationMatch, case_id: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "entity_id": match.entity.id,
        "entity_name": entity_display_name(match.entity.entity_type, match.entity.data),
        "entity_type": match.entity.entity_type,
        "match_type": match.kind.value,
        "case_id": case_id,
        "matches": [],
    }
    if match.kind is CorrelationKind.EMPLOYER:
        payload["employer_name"] = match.value
    elif match.kind is CorrelationKind.DOMAIN:
        payload["domain"] = match.value
    elif match.kind in {CorrelationKind.VIN, CorrelationKind.LICENSE_PLATE}:
        payload["matched_value"] = match.value
    return payload


def _other_entity_payload(match: CorrelationMatch) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "entity_id": match.other_entity.id,
        "entity_type": match.other_entity.entity_type,
        "case_id": match.other_case.id,
        "case_number": match.other_case.case_number,
        "case_title": match.other_case.title,
    }
    other_name = entity_display_name(
        match.other_entity.entity_type, match.other_entity.data
    )
    if match.kind is CorrelationKind.EMPLOYER:
        payload["person_name"] = other_name
    elif match.kind is CorrelationKind.DOMAIN:
        payload["entity_name"] = other_name
        payload["found_in"] = match.found_in
    elif match.kind in {CorrelationKind.VIN, CorrelationKind.LICENSE_PLATE}:
        payload["entity_name"] = other_name
        payload["matched_value"] = match.value
    return payload
