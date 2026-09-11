"""Plugin-catalogue adapter for the entity-correlation query."""

import asyncio
import hashlib
import json
from collections.abc import AsyncGenerator
from dataclasses import asdict
from typing import Any

from app.core.exceptions import BaseException as DomainException
from app.core.utils import get_utc_now
from app.database.models import Case
from app.services.entity_correlation import (
    CorrelationKind,
    CorrelationMatch,
    EntityCorrelation,
    ScanProgress,
    correlation_label,
)

from .base_plugin import BasePlugin, PluginRun, ResultEvent
from .output_limits import OutputBudget, OutputLimitExceeded, serialized_size


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
        executed_at = get_utc_now().isoformat()
        metadata = {
            "case_title": case.title,
            "case_number": case.case_number,
            "executed_at": executed_at,
        }
        event_limit = OutputBudget().event_limit
        pending: dict[str, Any] | None = None
        pending_size = 0
        try:
            correlation = EntityCorrelation(ctx.session)
            for item in correlation.iter_correlations(case, ctx.user):
                if isinstance(item, ScanProgress):
                    # No related counts are published without their Case scope.
                    await asyncio.sleep(0)
                    yield ResultEvent(
                        "status",
                        {
                            "message": item.message,
                            "count": item.count,
                            "case_scope": list(item.case_scope),
                        },
                    )
                    continue
                group = {**_group_payload(item, ctx.case_id), **metadata}
                other = _other_entity_payload(item)
                if pending is not None and pending["group_id"] != group["group_id"]:
                    await asyncio.sleep(0)
                    yield self.data(pending)
                    pending = None
                if pending is None:
                    pending = group
                    pending_size = serialized_size(self.data(pending).to_wire())
                added_size = serialized_size(other) + bool(pending["matches"])
                if pending_size + added_size > event_limit:
                    if pending["matches"]:
                        await asyncio.sleep(0)
                        yield self.data(pending)
                    pending = group
                    pending_size = serialized_size(self.data(pending).to_wire())
                    added_size = serialized_size(other)
                    if pending_size + added_size > event_limit:
                        raise OutputLimitExceeded("event_size_limit", event_limit)
                pending["matches"].append(other)
                pending_size += added_size
            if pending is not None:
                await asyncio.sleep(0)
                yield self.data(pending)
        except DomainException as error:
            yield self.error(str(error))
            return
        for warning in correlation.skipped_references:
            yield self.data(
                {
                    "notice_type": "skipped_reference",
                    "message": "A malformed reference was skipped; reference coverage is incomplete.",
                    "case_scope": sorted({ctx.case_id, warning.case_id}),
                    "case_id": warning.case_id,
                    "entity_id": warning.entity_id,
                    "field": warning.field,
                    "source_case_id": ctx.case_id,
                    "source_case_title": metadata["case_title"],
                    "source_case_number": metadata["case_number"],
                    "executed_at": executed_at,
                }
            )

    def correlation_case_ids(
        self, payloads: list[dict[str, Any]], case_id: int
    ) -> tuple[int, ...]:
        return tuple(
            sorted(
                {case_id}
                | {
                    match["case_id"]
                    for group in payloads
                    for match in group.get("matches", [])
                }
                | {
                    scope
                    for payload in payloads
                    for scope in payload.get("case_scope", [])
                }
            )
        )

    def format_evidence(
        self, results: list[dict[str, Any]], params: dict[str, Any]
    ) -> str:
        """Render browser-shaped correlation payloads as saved evidence."""
        del params
        if not results:
            return ""
        groups = assemble_groups([result for result in results if "matches" in result])
        first = results[0]
        source_id = first.get("source_case_id", first.get("case_id"))
        source_title = first.get("source_case_title", first.get("case_title", ""))
        source_number = first.get("source_case_number", first.get("case_number", ""))
        lines = [
            "Correlation Scan Results",
            "=" * 50,
            f"Total entities with matches: {len({group['entity_id'] for group in groups})}",
            f"Total matches: {sum(len(group['matches']) for group in groups)}",
            f"Related Cases: {len({match['case_id'] for group in groups for match in group['matches']})}",
            f"Source Case: {source_title} (#{source_number}); Case ID: {source_id}",
            f"Execution time: {first.get('executed_at', 'Not recorded')}",
            "",
        ]
        report_sections = [
            {**group, "matches": selected, "weak": weak}
            for weak in (False, True)
            for group in groups
            if (
                selected := [
                    match
                    for match in group["matches"]
                    if _weak_provider_match(match) == weak
                ]
            )
        ]
        for group in report_sections:
            if group["weak"]:
                lines.append(f"Weak provider matches ({len(group['matches'])})")
            lines.extend(
                [
                    f"Entity: {group['entity_name']}; Entity ID: {group['entity_id']}",
                    f"Type: {group['entity_type']}",
                    f"Match Type: {group['match_type']}",
                    f"Matched value: {group.get('matched_value', group.get('domain', group.get('employer_name', '')))}",
                    f"Normalized value: {group.get('normalized_value', '')}",
                    "Source fields: " + _format_fields(group.get("source_fields", [])),
                ]
            )
            for match in group["matches"]:
                lines.extend(
                    [
                        f"Case: {match['case_title']} (#{match['case_number']}); Case ID: {match['case_id']}",
                        f"Entity: {match.get('entity_name', match.get('person_name', 'Unnamed'))}; Entity ID: {match['entity_id']}",
                        f"Type: {match['entity_type']}",
                        "Related fields: " + _format_fields(match.get("fields", [])),
                        f"Qualification: {match.get('signal', 'Shared value association')}",
                    ]
                )
            lines.extend(["", "=" * 50, ""])
        for notice in results:
            if notice.get("notice_type") == "skipped_reference":
                lines.append(
                    f"{notice['message']} Case ID: {notice['case_id']}; Entity ID: {notice['entity_id']}; field: {notice['field']}"
                )
        return "\n".join(lines)


def _weak_provider_match(match: dict[str, Any]) -> bool:
    return match.get("signal_rank") == 2 or (
        "signal_rank" not in match
        and "low signal: common email provider" in match.get("signal", "").lower()
    )


def _format_fields(fields: list[dict[str, str]]) -> str:
    return "; ".join(f"{field['field']}: {field['value']}" for field in fields)


def assemble_groups(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reassemble additive continuation payloads; legacy groups stay readable."""
    groups: dict[str, dict[str, Any]] = {}
    matches: dict[str, dict[tuple[int, int], dict[str, Any]]] = {}
    for index, part in enumerate(parts):
        key = part.get("group_id", f"legacy:{index}")
        if key not in groups:
            groups[key] = {**part, "source_fields": [], "matches": []}
            matches[key] = {}
        groups[key]["source_fields"] = _merge_fields(
            groups[key]["source_fields"], part.get("source_fields", [])
        )
        for match in part["matches"]:
            identity = (match["case_id"], match["entity_id"])
            if identity not in matches[key]:
                matches[key][identity] = dict(match)
                groups[key]["matches"].append(matches[key][identity])
            previous = matches[key][identity]
            if "fields" in match:
                previous["fields"] = _merge_fields(
                    previous.get("fields", []), match["fields"]
                )
    for group in groups.values():
        group["matches"].sort(
            key=lambda match: (
                match.get("signal_rank", 1),
                match["case_id"],
                match["entity_id"],
            )
        )
    return sorted(
        groups.values(),
        key=lambda group: (
            min((match.get("signal_rank", 1) for match in group["matches"]), default=1),
            group["entity_id"],
            group["match_type"],
            group.get("normalized_value", ""),
        ),
    )


def _merge_fields(
    first: list[dict[str, str]], second: list[dict[str, str]]
) -> list[dict[str, str]]:
    return list(
        {
            (field["field"], field["value"]): field for field in (*first, *second)
        }.values()
    )


def _group_payload(match: CorrelationMatch, case_id: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "group_id": hashlib.sha256(
            json.dumps(
                [
                    case_id,
                    match.source_entity.id,
                    match.kind.value,
                    match.normalized_value,
                ],
                ensure_ascii=False,
            ).encode()
        ).hexdigest(),
        "continuation": "merge",
        "entity_id": match.source_entity.id,
        "entity_name": correlation_label(match.source_entity),
        "entity_type": match.source_entity.entity_type,
        "match_type": match.kind.value,
        "case_id": case_id,
        "normalized_value": match.normalized_value,
        "matched_value": match.value,
        "source_fields": [asdict(field) for field in match.source_fields],
        "matches": [],
    }
    if match.kind is CorrelationKind.EMPLOYER:
        payload["employer_name"] = match.value
    elif match.kind is CorrelationKind.DOMAIN:
        payload["domain"] = match.value
    return payload


def _other_entity_payload(match: CorrelationMatch) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "entity_id": match.other_entity.id,
        "entity_type": match.other_entity.entity_type,
        "entity_name": correlation_label(match.other_entity),
        "case_id": match.other_case.id,
        "case_number": match.other_case.case_number,
        "case_title": match.other_case.title,
        "fields": [asdict(field) for field in match.other_fields],
        "found_in": match.found_in,
        "matched_value": match.other_fields[0].value,
        "signal": match.signal,
        "signal_rank": match.signal_rank,
    }
    if match.kind is CorrelationKind.EMPLOYER:
        payload["person_name"] = payload["entity_name"]
    return payload
