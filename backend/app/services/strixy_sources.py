"""Bounded Case material projected through both readers' existing source policies."""

import hashlib
import json
from dataclasses import dataclass
from typing import cast

from sqlmodel import Session, col, select

from app.core.exceptions import AuthorizationException, ResourceNotFoundException
from app.core.strixy_config import StrixyConfig
from app.core.utils import get_utc_now
from app.database import models as m
from app.database.correlation_provenance import report_provenance
from app.executions.correlation_visibility import (
    CORRELATION_PLUGIN,
    CorrelationVisibility,
)
from app.executions.results import HuntResultReader
from app.services.case_access import CaseAccess
from app.services.evidence_service import EvidenceService
from app.services.strixy_access import require_strixy_access

SourceRow = (
    m.Case
    | m.Entity
    | m.Evidence
    | m.PluginExecutionResult
    | m.HuntStepResult
    | m.HuntStep
)

SOURCE_MODELS: dict[str, type[SourceRow]] = {
    "case": m.Case,
    "entity": m.Entity,
    "evidence": m.Evidence,
    "plugin_result": m.PluginExecutionResult,
    "hunt_result": m.HuntStepResult,
    "hunt_step": m.HuntStep,
}


def encoded(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


@dataclass
class CaseSource:
    kind: str
    id: int
    fields: dict[str, str]
    case_ids: list[int]
    version: str
    attachment: bool = False

    @property
    def source_id(self) -> str:
        return f"{self.kind}:{self.id}"

    def reference(self) -> dict:
        return {
            "source_id": self.source_id,
            "case_ids": self.case_ids,
            "version": self.version,
        }

    def view(self) -> dict:
        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "fields": self.fields,
            "version": self.version,
            "attachment": "unexamined" if self.attachment else None,
        }


class CaseSources:
    """Read only the active Case; related Case IDs authorize, never trigger retrieval."""

    def __init__(self, db: Session, human: m.User, case_id: int):
        self.db, self.human, self.case_id = db, human, case_id
        self.strixy = require_strixy_access(db, human, case_id)
        self.readers = (human, self.strixy)

    def read(self, source_id: str) -> CaseSource:
        try:
            kind, identifier = source_id.split(":")
            model = SOURCE_MODELS[kind]
            if not identifier.isdecimal() or int(identifier) <= 0:
                raise ValueError
        except (ValueError, KeyError):
            raise ResourceNotFoundException("Source unavailable") from None
        row = cast(
            SourceRow | None,
            self.db.get(model, int(identifier), populate_existing=True),
        )
        if row is None:
            raise ResourceNotFoundException("Source unavailable")
        scope = {self.case_id}
        attachment = False
        fields: dict
        if isinstance(row, m.PluginExecutionResult):
            execution = self.db.get(
                m.PluginExecution, row.execution_id, populate_existing=True
            )
            if execution is None or execution.case_id != self.case_id:
                raise ResourceNotFoundException("Source unavailable")
            payload = row.payload
            if execution.plugin_name == CORRELATION_PLUGIN:
                payload, represented = self._correlation(payload)
                scope.update(represented)
            if payload.get("type") != "data":
                raise ResourceNotFoundException("Source unavailable")
            fields = {"plugin": execution.plugin_name, "result": payload["data"]}
        elif isinstance(row, (m.HuntStep, m.HuntStepResult)):
            step = (
                row
                if isinstance(row, m.HuntStep)
                else self.db.get(m.HuntStep, row.step_id, populate_existing=True)
            )
            hunt_execution = (
                self.db.get(m.HuntExecution, step.execution_id, populate_existing=True)
                if step
                else None
            )
            if (
                step is None
                or hunt_execution is None
                or hunt_execution.case_id != self.case_id
            ):
                raise ResourceNotFoundException("Source unavailable")
            for user in self.readers:
                reader = HuntResultReader(self.db, hunt_execution, user)
                if not reader.can_read(step.step_id):
                    raise AuthorizationException("Source unavailable")
                scope.update(reader.scope.inherited(step.step_id) or ())
            if isinstance(row, m.HuntStepResult):
                payload = row.payload
                if step.output is not None:
                    raise ResourceNotFoundException("Source unavailable")
            else:
                if row.output is None:
                    raise ResourceNotFoundException("Source unavailable")
                payload = {"type": "data", "data": row.output}
            if step.plugin_name == CORRELATION_PLUGIN:
                if isinstance(row, m.HuntStep):
                    output = payload["data"]
                    filtered = []
                    for item in output.get("results", []):
                        try:
                            event, represented = self._correlation(
                                {"type": "data", "data": item}
                            )
                        except ResourceNotFoundException:
                            continue
                        filtered.append(event["data"])
                        scope.update(represented)
                    if not filtered:
                        raise ResourceNotFoundException("Source unavailable")
                    payload = {
                        "type": "data",
                        "data": {
                            "results": filtered,
                            "partial": bool(output.get("partial")),
                        },
                    }
                else:
                    payload, represented = self._correlation(payload)
                    scope.update(represented)
            if payload.get("type") != "data":
                raise ResourceNotFoundException("Source unavailable")
            fields = {"plugin": step.plugin_name, "result": payload["data"]}
        else:
            if (row.id if isinstance(row, m.Case) else row.case_id) != self.case_id:
                raise ResourceNotFoundException("Source unavailable")
            if isinstance(row, m.Evidence):
                for user in self.readers:
                    EvidenceService(self.db).require_read(row, user)
                provenance = report_provenance(self.db, row)
                if provenance:
                    scope.update(provenance.case_ids or ())
                attachment = not row.is_folder
                fields = {
                    "title": row.title,
                    "description": row.description,
                    "evidence_type": row.evidence_type,
                    "category": row.category,
                    "is_folder": row.is_folder,
                }
            elif isinstance(row, m.Entity):
                fields = {"entity_type": row.entity_type, "data": row.data}
            else:
                assert isinstance(row, m.Case)
                fields = {
                    "case_number": row.case_number,
                    "title": row.title,
                    "status": row.status,
                    "notes": row.notes,
                }
        rendered = {
            key: value if isinstance(value, str) else encoded(value)
            for key, value in fields.items()
        }
        version = hashlib.sha256(
            encoded([rendered, getattr(row, "updated_at", None)]).encode()
        ).hexdigest()
        return CaseSource(
            kind, int(identifier), rendered, sorted(scope), version, attachment
        )

    def _correlation(self, payload: dict) -> tuple[dict, set[int]]:
        for user in self.readers:
            projected = CorrelationVisibility(self.db, user, self.case_id).event(
                payload
            )
            if projected is None:
                raise ResourceNotFoundException("Source unavailable")
            payload = projected
        data = payload.get("data", {})
        scope = set(data.get("case_scope", [self.case_id]))
        scope.update(match["case_id"] for match in data.get("matches", []))
        return payload, scope

    def catalog(self, config: StrixyConfig) -> tuple[list[CaseSource], bool]:
        sources = [self.read(f"case:{self.case_id}")]
        complete = True
        queries = {
            "entity": select(m.Entity.id).where(m.Entity.case_id == self.case_id),
            "evidence": select(m.Evidence.id).where(m.Evidence.case_id == self.case_id),
            "plugin_result": select(m.PluginExecutionResult.id)
            .join(m.PluginExecution)
            .where(m.PluginExecution.case_id == self.case_id),
            "hunt_step": select(m.HuntStep.id)
            .join(m.HuntExecution)
            .where(
                m.HuntExecution.case_id == self.case_id,
            ),
            "hunt_result": select(m.HuntStepResult.id)
            .join(m.HuntStep)
            .join(m.HuntExecution)
            .where(
                m.HuntExecution.case_id == self.case_id,
            ),
        }
        for kind, query in queries.items():
            rows = self.db.exec(
                query.order_by(col(SOURCE_MODELS[kind].id)).limit(
                    config.max_source_scan + 1
                )
            ).all()
            if len(rows) > config.max_source_scan:
                complete = False
            for identifier in rows[: config.max_source_scan]:
                try:
                    source = self.read(f"{kind}:{identifier}")
                except (AuthorizationException, ResourceNotFoundException):
                    continue
                if len(sources) >= config.max_sources:
                    return sources, False
                sources.append(source)
        return sources, complete

    def validate_provenance(
        self, references: list[dict], *, current: bool = False
    ) -> bool:
        """Pinned historical scope remains required even if today's source is edited."""
        try:
            for ref in references:
                for user in self.readers:
                    for case_id in ref["case_ids"]:
                        CaseAccess(self.db).readable(user, case_id)
                source = self.read(ref["source_id"])
                if current and source.version != ref["version"]:
                    return False
        except (AuthorizationException, ResourceNotFoundException):
            return False
        return True


class GroundedMaterial:
    """Record exactly which bounded fields were offered to the model."""

    def __init__(
        self,
        sources: list[CaseSource],
        complete: bool,
        config: StrixyConfig,
        focus: list[str],
    ):
        self.sources = {s.source_id: s for s in sources}
        if set(focus) - self.sources.keys():
            raise ResourceNotFoundException("Focus source unavailable")
        self.focus = focus
        self.complete = complete
        self.config = config
        self.inspected_at = get_utc_now().isoformat()
        self.supplied: dict[str, dict] = {}
        self.tool_result: dict | None = None
        self.states = {key: "unexamined" for key in self.sources}
        self.remaining = config.max_source_bytes
        for source_id in focus or list(self.sources):
            self.read(source_id)

    def read(self, source_id: str):
        if source_id not in self.sources or (
            self.focus and source_id not in self.focus
        ):
            raise ResourceNotFoundException("Source unavailable")
        if source_id in self.supplied:
            return
        source = self.sources[source_id]
        if self.remaining < 256:
            return
        fields = {}
        partial = False
        budget = min(self.config.max_source_field_bytes, self.remaining - 256)
        for key, value in source.fields.items():
            raw = value.encode()
            fields[key] = raw[:budget].decode("utf-8", errors="ignore")
            budget -= len(fields[key].encode())
            partial |= fields[key] != value
        view = source.view() | {"fields": fields}
        size = len(encoded(view).encode())
        if size > self.remaining:
            return
        self.remaining -= size
        self.supplied[source_id] = view
        self.states[source_id] = "partly_read" if partial else "read"

    def lookup(self, source_id: str):
        self.read(source_id)
        self.tool_result = {
            "action": "read",
            "source_ids": [source_id],
            "state": self.states[source_id],
        }

    def list_sources(self):
        self.tool_result = {
            "action": "list",
            "source_ids": list(self.sources),
            "enumeration_complete": self.complete,
        }

    def search(self, query: str):
        matches = []
        for source in self.sources.values():
            if self.focus and source.source_id not in self.focus:
                continue
            if query.casefold() in encoded(source.fields).casefold():
                self.read(source.source_id)
                matches.append(source.source_id)
        self.tool_result = {
            "action": "search",
            "query": query,
            "source_ids": matches,
            "enumeration_complete": self.complete,
        }

    def context(self) -> dict:
        return {
            "tool_result": self.tool_result,
            "sources": list(self.supplied.values()),
            "coverage": self.coverage(),
            "catalog": [
                {"source_id": key, "kind": s.kind}
                for key, s in self.sources.items()
                if not self.focus or key in self.focus
            ],
        }

    def coverage(self) -> dict:
        return {
            "mode": "focused" if self.focus else "broad",
            "enumeration_complete": self.complete,
            "attachments": "unexamined",
            "complete": self.complete
            and not self.focus
            and all(v == "read" for v in self.states.values())
            and not any(s.attachment for s in self.sources.values()),
            "counts": {
                state: list(self.states.values()).count(state)
                for state in ("read", "partly_read", "unexamined", "unavailable")
            },
            "sources": [
                {"source_id": key, "state": state} for key, state in self.states.items()
            ],
        }

    def provenance(self) -> list[dict]:
        # Catalog IDs and coverage are model inputs too, even when uncited/unread.
        return [s.reference() for s in self.sources.values()]

    def citations(self, citations: list[dict]) -> list[dict]:
        result = []
        for citation in citations:
            if set(citation) != {"source_id", "field", "excerpt"}:
                raise ValueError("Invalid citation")
            source = self.supplied.get(citation["source_id"])
            excerpt = citation["excerpt"]
            if (
                source is None
                or citation["field"] not in source["fields"]
                or not isinstance(excerpt, str)
                or not excerpt
                or excerpt not in source["fields"][citation["field"]]
            ):
                raise ValueError("Invalid citation")
            result.append(
                citation
                | {"version": source["version"], "inspected_at": self.inspected_at}
            )
        return result
