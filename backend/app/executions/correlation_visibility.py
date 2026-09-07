"""Viewer-specific projection of correlation output; persisted bytes stay untouched.

Group fields describe the source Case; each match describes its stored case_id.
Non-group notices must carry server-produced case_scope (all Cases represented).
Unscoped legacy status/summary text is discarded and errors use safe fixed text.
New payload fields must be assigned to one of these scopes before being exposed.
"""

from sqlmodel import Session

from app.database.models import User
from app.services.case_access import CaseAccess

CORRELATION_PLUGIN = "CorrelationScan"
CORRELATION_ERROR = (
    "Correlation scan could not complete. Available results may be partial."
)
GROUP_FIELDS = {
    "case_id",
    "entity_id",
    "entity_name",
    "entity_type",
    "match_type",
    "case_title",
    "case_number",
    "executed_at",
    "normalized_value",
    "source_fields",
    "employer_name",
    "domain",
    "matched_value",
}
MATCH_FIELDS = {
    "case_id",
    "case_number",
    "case_title",
    "entity_id",
    "entity_type",
    "entity_name",
    "person_name",
    "fields",
    "signal",
    "found_in",
    "matched_value",
}


def safe_error(error: dict | None) -> dict | None:
    if error is None:
        return None
    result = {"message": CORRELATION_ERROR}
    if error.get("code") in {
        "output_limit_exceeded",
        "dispatch_failed",
        "worker_interrupted",
        "cancelled",
    }:
        result["code"] = error["code"]
    return result


class CorrelationVisibility:
    """Resolve CaseAccess once per read, then project every event on that read."""

    def __init__(self, db: Session, user: User, source_case_id: int):
        access = CaseAccess(db)
        access.readable(user, source_case_id)
        self.source_case_id = source_case_id
        self.readable = set(access.readable_case_ids(user))

    def group(self, payload: dict) -> dict | None:
        if payload.get("case_id") != self.source_case_id:
            return None
        matches = [
            {key: value for key, value in match.items() if key in MATCH_FIELDS}
            for match in payload.get("matches", [])
            if isinstance(match, dict)
            and type(match.get("case_id")) is int
            and match["case_id"] in self.readable
        ]
        if not matches:
            return None
        return {
            **{key: value for key, value in payload.items() if key in GROUP_FIELDS},
            "matches": matches,
        }

    def event(self, event: dict) -> dict | None:
        kind, payload = event.get("type"), event.get("data") or {}
        if kind == "data" and isinstance(payload.get("matches"), list):
            group = self.group(payload)
            return {"type": "data", "data": group} if group else None
        if kind == "complete":
            return {"type": "complete", "data": {}}
        if kind == "error":
            return {"type": "error", "data": safe_error(payload)}
        scope = payload.get("case_scope")
        if (
            kind in {"data", "status"}
            and isinstance(scope, list)
            and scope
            and all(
                type(case_id) is int and case_id in self.readable for case_id in scope
            )
        ):
            return {"type": kind, "data": payload}
        return None

    def events(self, events: list[dict]) -> list[dict]:
        return [
            visible for event in events if (visible := self.event(event)) is not None
        ]

    def output(self, output: dict | None) -> dict | None:
        if output is None:
            return None
        results = [
            event["data"]
            for event in self.events(
                [
                    {"type": "data", "data": payload}
                    for payload in output.get("results", [])
                ]
            )
        ]
        return {
            "results": results,
            "result_count": len(results),
            "plugin": CORRELATION_PLUGIN,
            "errors": [safe_error(error) for error in output.get("errors", [])],
            **({"partial": True} if output.get("partial") else {}),
        }
