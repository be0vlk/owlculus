"""Bounded Case material projected through both readers' existing source policies."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic
from typing import Literal, cast

from pydantic import BaseModel, Field
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
from app.schemas.entity_schema import entity_display_name
from app.schemas.strixy_schema import VisualInput
from app.services.case_access import CaseAccess
from app.services.evidence_service import EvidenceService
from app.services.strixy_access import require_strixy_access
from app.services.strixy_attachments import Attachment, prepare

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
    stored_attachment: Attachment | None = None
    prepared: dict | None = None

    @property
    def source_id(self) -> str:
        return f"{self.kind}:{self.id}"

    def reference(self) -> dict:
        return {
            "source_id": self.source_id,
            "case_ids": self.case_ids,
            "version": self.version,
        }

    def catalog_entry(self) -> dict:
        """Small display labels derived only from this already-authorized projection."""
        title = ""
        subtitle = self.kind.replace("_", " ").capitalize()
        if self.kind == "entity":
            entity_type = self.fields.get("entity_type", "entity")
            data = json.loads(self.fields.get("data", "{}"))
            if isinstance(data, dict):
                title = entity_display_name(entity_type, data) or str(
                    data.get("name") or ""
                )
            subtitle = entity_type.replace("_", " ").capitalize()
        elif self.kind in {"case", "evidence"}:
            title = self.fields.get("title", "")
            subtitle = (
                self.fields.get("case_number", "Case")
                if self.kind == "case"
                else (
                    "Evidence folder"
                    if self.fields.get("is_folder") == "true"
                    else "Evidence"
                )
            )
        else:
            title = self.fields.get("plugin", "")
        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "title": " ".join(title.split())[:200] or f"{subtitle} #{self.id}",
            "subtitle": subtitle[:100],
        }

    def view(self) -> dict:
        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "fields": self.fields,
            "version": self.version,
            "attachment": self.prepared or ("unexamined" if self.attachment else None),
        }


class MaterialCheckpoint(BaseModel):
    """Version-checked preparation state; cursors are internal, never model inputs."""

    supplied: dict[str, dict] = Field(default_factory=dict)
    images: list[VisualInput] = Field(default_factory=list)
    states: dict[str, Literal["read", "partly_read", "unexamined", "unavailable"]] = (
        Field(default_factory=dict)
    )
    exhausted_sources: list[str] = Field(default_factory=list)
    offsets: dict[str, dict[str, int]] = Field(default_factory=dict)
    cursor: dict[str, int] = Field(default_factory=dict)
    next_cursor: dict[str, int] = Field(default_factory=dict)
    enumeration_complete: bool = False

    def exhausted(self) -> set[str]:
        # Older checkpoints already identify completely supplied sources as read.
        return set(self.exhausted_sources) | {
            key for key, state in self.states.items() if state == "read"
        }

    def batch_exhausted(self) -> bool:
        return self.states.keys() <= self.exhausted()


@dataclass
class SourceCatalog:
    sources: list[CaseSource]
    complete: bool
    cursor: dict[str, int] = field(default_factory=dict)
    limits: list[str] = field(default_factory=list)


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
        stored_attachment = (
            Attachment.locate(self.case_id, row.content)
            if isinstance(row, m.Evidence) and attachment
            else None
        )
        version = hashlib.sha256(
            encoded(
                [
                    rendered,
                    getattr(row, "updated_at", None),
                    stored_attachment.version if stored_attachment else None,
                ]
            ).encode()
        ).hexdigest()
        return CaseSource(
            kind,
            int(identifier),
            rendered,
            sorted(scope),
            version,
            attachment,
            stored_attachment,
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

    def catalog(
        self, config: StrixyConfig, cursor: dict[str, int] | None = None
    ) -> SourceCatalog:
        after = dict(cursor or {})
        sources = []
        if "case" not in after:
            sources.append(self.read(f"case:{self.case_id}"))
            after["case"] = self.case_id
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
                query.where(col(SOURCE_MODELS[kind].id) > after.get(kind, 0))
                .order_by(col(SOURCE_MODELS[kind].id))
                .limit(config.max_source_scan + 1)
            ).all()
            for identifier in rows[: config.max_source_scan]:
                if len(sources) >= config.max_sources:
                    return SourceCatalog(sources, False, after, ["source_count_limit"])
                assert identifier is not None
                after[kind] = identifier
                try:
                    source = self.read(f"{kind}:{identifier}")
                except (AuthorizationException, ResourceNotFoundException):
                    continue
                sources.append(source)
            if len(rows) > config.max_source_scan:
                return SourceCatalog(sources, False, after, ["source_scan_limit"])
        return SourceCatalog(sources, True, after)

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
        previous: MaterialCheckpoint | None = None,
        catalog: SourceCatalog | None = None,
        cursor: dict[str, int] | None = None,
        preparation_timeout: float | None = None,
        before_attachment: Callable[[CaseSource], None] | None = None,
        attachment_start: int = 0,
    ):
        self.attachment_start = attachment_start
        self.before_attachment = before_attachment
        self.preparation_deadline = monotonic() + min(
            config.attachment_seconds,
            (
                preparation_timeout
                if preparation_timeout is not None
                else config.attachment_seconds
            ),
        )
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
        self.previous = previous or MaterialCheckpoint()
        # Cumulative processing is independent of what fits this model input.
        # Incomplete but exhausted attachments still retain their honest coverage.
        self.exhausted_sources = self.previous.exhausted() & self.sources.keys()
        self.catalog = catalog or SourceCatalog(sources, complete)
        self.cursor = cursor or {}
        self.limits = set(self.catalog.limits)
        self.offsets = {
            key: value
            for key, value in self.previous.offsets.items()
            if key in self.sources
        }
        self.reused_progress = bool(previous)
        self.remaining = config.max_source_bytes
        self.images: list[VisualInput] = []
        self.visual_remaining = config.visual_max_input_bytes
        ordered = focus or list(self.sources)
        if previous:
            ordered = sorted(ordered, key=lambda key: key in self.exhausted_sources)
        for source_id in ordered:
            self.read(source_id)

    def read(self, source_id: str):
        if source_id not in self.sources or (
            self.focus and source_id not in self.focus
        ):
            raise ResourceNotFoundException("Source unavailable")
        if source_id in self.supplied:
            return
        source = self.sources[source_id]
        cached = self.previous.supplied.get(source_id)
        if source_id in self.exhausted_sources:
            if not cached:
                return
            size = len(encoded(cached).encode())
            images = [v for v in self.previous.images if v.source_id == source_id]
            visual_size = sum(len(v.data) for v in images)
            if (
                size <= self.remaining
                and visual_size <= self.visual_remaining
                and len(self.images) + len(images) <= self.config.visual_max_images
            ):
                self.images.extend(images)
                self.visual_remaining -= visual_size
                self.supplied[source_id] = cached
                self.states[source_id] = self.previous.states[source_id]
                self.remaining -= size
            else:
                self.limits.add("source_bytes_limit")
            return
        if self.remaining < 256:
            self.limits.add("source_bytes_limit")
            return
        prepared_images = []
        if source.stored_attachment:
            if self.before_attachment:
                self.before_attachment(source)
            prior = (cached or {}).get("attachment") or {}
            start = prior.get("start_unit", self.attachment_start)
            if (
                prior.get("reason") in {"attachment_unit_limit", "visual_input_limit"}
                and prior.get("next_unit", 0) > start
                and not prior.get("text_truncated")
            ):
                start = prior["next_unit"]
                self.offsets.pop(source_id, None)
            prepared = prepare(
                source.stored_attachment,
                self.config.model_copy(
                    update={
                        "visual_max_images": self.config.visual_max_images
                        - len(self.images),
                        "visual_max_input_bytes": self.visual_remaining,
                    }
                ),
                start=start,
                timeout=self.preparation_deadline - monotonic(),
            )
            prepared_images = [
                VisualInput(source_id=source_id, **image) for image in prepared.images
            ]
            source.fields.update(prepared.fields)
            source.prepared = prepared.view() | {"start_unit": start}
            if prepared.reason and prepared.reason.endswith("_limit"):
                self.limits.add(prepared.reason)
        fields = {}
        partial = False
        field_limit = self.config.max_source_field_bytes <= self.remaining - 256
        budget = min(self.config.max_source_field_bytes, self.remaining - 256)
        offsets = dict(self.offsets.get(source_id, {}))
        for key, value in source.fields.items():
            offset = offsets.get(key, 0)
            raw = value.encode()[offset:]
            fields[key] = raw[:budget].decode("utf-8", errors="ignore")
            budget -= len(fields[key].encode())
            offsets[key] = offset + len(fields[key].encode())
            partial |= offsets[key] < len(value.encode())
        view = source.view() | {"fields": fields}
        if (
            source.prepared
            and partial
            and any(key.startswith("attachment:") for key in fields)
        ):
            view["attachment"] = source.prepared | {
                "state": "partly_read",
                "text_truncated": True,
            }
        if prepared_images:
            view["visual_fields"] = [v.field for v in prepared_images]
        size = len(encoded(view).encode())
        if size > self.remaining:
            self.limits.add("source_bytes_limit")
            return
        self.images.extend(prepared_images)
        self.visual_remaining -= sum(len(v.data) for v in prepared_images)
        self.remaining -= size
        self.offsets[source_id] = offsets
        self.supplied[source_id] = view
        attachment_partial = source.prepared and source.prepared["state"] != "read"
        self.states[source_id] = (
            "partly_read" if partial or attachment_partial else "read"
        )
        # Unit, time and model-input budgets reset on an explicit continuation.
        # Fixed format/size limitations and warnings cannot be improved by reading
        # the same unchanged attachment again; reanalysis can retry those outcomes.
        resumable_attachment = source.prepared and source.prepared["reason"] in {
            "attachment_unit_limit",
            "visual_input_limit",
            "attachment_time_limit",
            "attachment_processing_limit",
            "source_changed",
        }
        if not partial and not resumable_attachment:
            self.exhausted_sources.add(source_id)
        if partial:
            self.limits.add(
                "source_field_limit" if field_limit else "source_bytes_limit"
            )

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
            "reused_progress": self.reused_progress,
            "tool_result": self.tool_result,
            "sources": list(self.supplied.values()),
            "coverage": self.coverage(),
            "catalog": [
                {"source_id": key, "kind": s.kind}
                for key, s in self.sources.items()
                if not self.focus or key in self.focus
            ],
        }

    def checkpoint(self) -> dict:
        return MaterialCheckpoint(
            supplied=self.supplied,
            images=self.images,
            states=self.states,
            exhausted_sources=sorted(self.exhausted_sources),
            offsets=self.offsets,
            cursor=self.cursor,
            next_cursor=self.catalog.cursor,
            enumeration_complete=self.complete,
        ).model_dump()

    def attachment_outcome(self, key: str) -> dict:
        outcome = self.supplied.get(key, {}).get("attachment")
        return outcome if isinstance(outcome, dict) else {"state": "unexamined"}

    def coverage(self) -> dict:
        attachments_read = all(
            not source.attachment or self.attachment_outcome(key).get("state") == "read"
            for key, source in self.sources.items()
        )
        return {
            "mode": "focused" if self.focus else "batch" if self.cursor else "broad",
            "limits": sorted(self.limits),
            "enumeration_complete": self.complete,
            "attachments": "examined" if attachments_read else "incomplete",
            "attachment_outcomes": [
                {"source_id": key, **self.attachment_outcome(key)}
                for key, s in self.sources.items()
                if s.attachment
            ],
            "complete": not self.reused_progress
            and self.complete
            and not self.focus
            and not self.cursor
            and all(v == "read" for v in self.states.values())
            and attachments_read,
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
            visual = any(
                v.source_id == citation["source_id"] and v.field == citation["field"]
                for v in self.images
            )
            if source is None or not isinstance(excerpt, str):
                raise ValueError("Invalid citation")
            if visual:
                if excerpt != "":
                    raise ValueError("Visual references cannot verify transcriptions")
            elif (
                citation["field"] not in source["fields"]
                or not excerpt
                or excerpt not in source["fields"][citation["field"]]
            ):
                raise ValueError("Invalid citation")
            result.append(
                citation
                | {"version": source["version"], "inspected_at": self.inspected_at}
                | ({"kind": "visual"} if visual else {})
            )
        return result
