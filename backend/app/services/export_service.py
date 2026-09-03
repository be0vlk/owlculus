"""Generate lossless, reusable exports for Owlculus case data."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from types import UnionType
from typing import Any, Union, get_args, get_origin

from bs4 import BeautifulSoup
from fpdf import FPDF
from fpdf.enums import WrapMode, XPos, YPos
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.core.dependencies import check_case_access, no_analyst
from app.core.exceptions import ResourceNotFoundException
from app.core.logging import get_security_logger
from app.core.utils import get_utc_now
from app.database import models
from app.schemas.entity_schema import ENTITY_TYPE_SCHEMAS, NetworkAssets


class _NetworkAssetsExportData(NetworkAssets):
    notes: str | None = None
    sources: dict[str, str] | None = None


ENTITY_EXPORT_SCHEMAS: dict[str, type[BaseModel]] = {
    "person": ENTITY_TYPE_SCHEMAS["person"],
    "company": ENTITY_TYPE_SCHEMAS["company"],
    "domain": ENTITY_TYPE_SCHEMAS["domain"],
    "ip_address": ENTITY_TYPE_SCHEMAS["ip_address"],
    "network_assets": _NetworkAssetsExportData,
    "vehicle": ENTITY_TYPE_SCHEMAS["vehicle"],
}

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
HUNT_OUTPUT_LIMIT_BYTES = 32 * 1024
HUNT_OUTPUT_TRUNCATION_NOTICE = (
    "[Output truncated. Full output is available in the JSON export.]"
)


@dataclass(frozen=True)
class ExportArtifact:
    """A complete in-memory download produced by an export writer."""

    content: bytes
    media_type: str
    filename: str


class EntityExportFormat(StrEnum):
    """Supported standalone entity export representations."""

    CSV = "csv"
    JSON = "json"


class HuntExecutionExportFormat(StrEnum):
    """Supported hunt execution export representations."""

    PDF = "pdf"
    JSON = "json"


class ExportService:
    """Own export access checks, filtering, serialization, and audit logging."""

    def __init__(self, db: Session):
        self.db = db

    def export_entities(
        self,
        case_id: int,
        current_user: models.User,
        export_format: EntityExportFormat,
        entity_types: list[str] | None = None,
        search: str | None = None,
    ) -> ExportArtifact:
        """Return every entity matching the supplied case-table filters."""
        case = check_case_access(self.db, case_id, current_user)
        entities = self._get_entities(case_id, entity_types, search)
        safe_case_number = filesystem_safe_name(case.case_number)
        export_date = get_utc_now().date().isoformat()

        if export_format is EntityExportFormat.JSON:
            content = self.write_entity_json(entities)
            media_type = "application/json"
        else:
            content = self.write_entity_csv(entities, empty_schema_types=entity_types)
            media_type = "text/csv; charset=utf-8"

        get_security_logger(
            user_id=current_user.id,
            requesting_user=current_user.username,
            case_id=case_id,
            export_kind="entities",
            format=export_format.value,
            event_type="export_generated",
        ).info("Entity export generated")

        return ExportArtifact(
            content=content,
            media_type=media_type,
            filename=f"{safe_case_number}-entities-{export_date}.{export_format.value}",
        )

    @no_analyst()
    def export_hunt_execution(
        self,
        execution_id: int,
        current_user: models.User,
        export_format: HuntExecutionExportFormat,
    ) -> ExportArtifact:
        """Return a backend-generated snapshot of a hunt execution."""
        execution = self.db.get(models.HuntExecution, execution_id)
        if execution is None:
            raise ResourceNotFoundException("Hunt execution not found")

        check_case_access(self.db, execution.case_id, current_user)
        representation = self._hunt_execution_representation(execution)
        hunt_name = filesystem_safe_name(representation["hunt"]["name"])
        exported_at = get_utc_now()
        export_logger = get_security_logger(
            user_id=current_user.id,
            requesting_user=current_user.username,
            case_id=execution.case_id,
            export_kind="hunt_execution",
            format=export_format.value,
        )
        try:
            if export_format is HuntExecutionExportFormat.PDF:
                content = self.write_hunt_execution_pdf(representation, exported_at)
                media_type = "application/pdf"
            else:
                content = self.write_hunt_execution_json(representation, exported_at)
                media_type = "application/json"
        except Exception:
            export_logger.bind(event_type="export_generation_failed").exception(
                "Hunt execution export failed"
            )
            raise

        export_logger.bind(
            event_type="export_generated",
        ).info("Hunt execution export generated")

        return ExportArtifact(
            content=content,
            media_type=media_type,
            filename=(
                f"hunt-execution-{execution_id}-{hunt_name}.{export_format.value}"
            ),
        )

    def write_hunt_execution_json(
        self, representation: dict[str, Any], exported_at: datetime
    ) -> bytes:
        """Serialize the stable, lossless hunt execution export envelope."""
        return json.dumps(
            {
                "execution": representation,
                "timestamp": _iso_utc(exported_at),
                "export_version": "1.0",
            },
            ensure_ascii=False,
        ).encode("utf-8")

    def write_hunt_execution_pdf(
        self, representation: dict[str, Any], exported_at: datetime
    ) -> bytes:
        """Render a standalone Unicode PDF report for a hunt execution."""
        pdf = _HuntExecutionPDF(_iso_utc(exported_at))
        pdf.add_font("DejaVu", fname=FONT_DIR / "DejaVuSans.ttf")
        pdf.add_font("DejaVuMono", fname=FONT_DIR / "DejaVuSansMono.ttf")
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.set_title(
            f"{representation['hunt']['display_name']} - "
            f"Execution #{representation['id']}"
        )
        pdf.add_page()

        pdf.set_font("DejaVu", size=18)
        _pdf_text(pdf, representation["hunt"]["display_name"], line_height=9)
        pdf.set_font("DejaVu", size=13)
        _pdf_text(pdf, f"Execution #{representation['id']}", line_height=7)
        pdf.ln(2)

        case = representation.get("case") or {}
        creator = representation.get("created_by") or {}
        title_details = [
            ("Case", f"{case.get('case_number', '')} - {case.get('title', '')}"),
            ("Status", representation["status"]),
            ("Progress", f"{representation['progress'] * 100:g}%"),
            ("Created by", creator.get("username", "")),
            ("Created", representation["created_at"]),
            ("Started", representation.get("started_at") or "Not started"),
            ("Completed", representation.get("completed_at") or "Not completed"),
            (
                "Duration",
                _duration_text(
                    representation.get("started_at"),
                    representation.get("completed_at"),
                ),
            ),
        ]
        _pdf_key_value_table(pdf, title_details)

        _pdf_heading(pdf, "Hunt")
        _pdf_key_value_table(pdf, [("Category", representation["hunt"]["category"])])
        pdf.set_font("DejaVu", size=10)
        _pdf_text(pdf, representation["hunt"]["description"])

        _pdf_heading(pdf, "Initial Parameters")
        initial_parameters = representation.get("initial_parameters") or {}
        if initial_parameters:
            _pdf_key_value_table(
                pdf,
                [
                    (str(key), _readable_value(value))
                    for key, value in initial_parameters.items()
                ],
            )
        else:
            _pdf_text(pdf, "No initial parameters")

        _pdf_heading(pdf, "Execution Steps")
        steps = representation.get("steps") or []
        if not steps:
            _pdf_text(pdf, "No steps recorded")
        for index, step in enumerate(steps, start=1):
            pdf.set_font("DejaVu", size=12)
            _pdf_text(
                pdf,
                f"Step {index}: {step['step_id']} ({step['plugin_name']})",
                line_height=7,
            )
            _pdf_key_value_table(
                pdf,
                [
                    ("Status", step["status"]),
                    ("Started", step.get("started_at") or "Not started"),
                    ("Completed", step.get("completed_at") or "Not completed"),
                    (
                        "Duration",
                        _duration_text(
                            step.get("started_at"), step.get("completed_at")
                        ),
                    ),
                    ("Retry count", str(step["retry_count"])),
                ],
            )
            pdf.set_font("DejaVu", size=10)
            _pdf_text(pdf, "Parameters")
            parameters = step.get("parameters") or {}
            if parameters:
                _pdf_key_value_table(
                    pdf,
                    [
                        (str(key), _readable_value(value))
                        for key, value in parameters.items()
                    ],
                )
            else:
                _pdf_text(pdf, "No parameters")

            if step.get("error_details"):
                pdf.set_text_color(160, 0, 0)
                _pdf_text(pdf, f"Error: {step['error_details']}")
                pdf.set_text_color(0, 0, 0)

            pdf.set_font("DejaVu", size=10)
            _pdf_text(pdf, "Output")
            output_text = json.dumps(
                step.get("output"), ensure_ascii=False, indent=2, default=str
            )
            output_text, truncated = _truncate_utf8(
                output_text, HUNT_OUTPUT_LIMIT_BYTES
            )
            if truncated:
                notice_size = len(HUNT_OUTPUT_TRUNCATION_NOTICE.encode("utf-8")) + 1
                output_text, _ = _truncate_utf8(
                    output_text, HUNT_OUTPUT_LIMIT_BYTES - notice_size
                )
                output_text = f"{output_text}\n{HUNT_OUTPUT_TRUNCATION_NOTICE}"
            pdf.set_fill_color(245, 245, 245)
            pdf.set_font("DejaVuMono", size=8)
            _pdf_text(pdf, output_text, line_height=4, fill=True)
            pdf.ln(2)

        evidence_references = _evidence_references(representation.get("context_data"))
        if evidence_references:
            _pdf_heading(pdf, "Evidence References")
            pdf.set_font("DejaVu", size=10)
            for title, folder_path in evidence_references:
                suffix = f" - {folder_path}" if folder_path else ""
                _pdf_text(pdf, f"• {title}{suffix}")

        return bytes(pdf.output())

    def _hunt_execution_representation(
        self, execution: models.HuntExecution
    ) -> dict[str, Any]:
        hunt = self.db.get(models.Hunt, execution.hunt_id)
        case = self.db.get(models.Case, execution.case_id)
        creator = self.db.get(models.User, execution.created_by_id)
        steps = list(
            self.db.exec(
                select(models.HuntStep)
                .where(models.HuntStep.execution_id == execution.id)
                .order_by(col(models.HuntStep.id))
            )
        )
        hunt_data = None
        if hunt is not None:
            hunt_data = {
                "id": hunt.id,
                "name": hunt.name,
                "display_name": hunt.display_name,
                "description": hunt.description,
                "category": hunt.category,
                "version": hunt.version,
                "is_active": hunt.is_active,
                "initial_parameters": hunt.definition_json.get(
                    "initial_parameters", {}
                ),
                "step_count": len(hunt.definition_json.get("steps", [])),
                "created_at": _iso_utc(hunt.created_at),
                "updated_at": _iso_utc(hunt.updated_at),
            }
        return {
            "id": execution.id,
            "hunt_id": execution.hunt_id,
            "case_id": execution.case_id,
            "status": execution.status,
            "progress": execution.progress,
            "initial_parameters": execution.initial_parameters,
            "context_data": execution.context_data,
            "started_at": _optional_iso_utc(execution.started_at),
            "completed_at": _optional_iso_utc(execution.completed_at),
            "created_at": _iso_utc(execution.created_at),
            "created_by_id": execution.created_by_id,
            "hunt": hunt_data,
            "steps": [
                {
                    "id": step.id,
                    "execution_id": step.execution_id,
                    "step_id": step.step_id,
                    "plugin_name": step.plugin_name,
                    "status": step.status,
                    "parameters": step.parameters,
                    "output": step.output,
                    "error_details": step.error_details,
                    "retry_count": step.retry_count,
                    "started_at": _optional_iso_utc(step.started_at),
                    "completed_at": _optional_iso_utc(step.completed_at),
                }
                for step in steps
            ],
            "case": (
                {
                    "id": case.id,
                    "title": case.title,
                    "case_number": case.case_number,
                }
                if case is not None
                else None
            ),
            "created_by": (
                {
                    "id": creator.id,
                    "email": creator.email,
                    "username": creator.username,
                }
                if creator is not None
                else None
            ),
        }

    def write_entity_csv(
        self,
        entities: list[models.Entity],
        empty_schema_types: list[str] | None = None,
    ) -> bytes:
        """Serialize entities as a flattened RFC 4180 spreadsheet."""
        columns = self._entity_csv_columns(entities, empty_schema_types)
        creator_names = self._creator_names(entities)
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\r\n")
        writer.writeheader()

        for entity in entities:
            data = entity.data
            row: dict[str, str] = {
                "id": str(entity.id),
                "entity_type": entity.entity_type,
                "display_name": entity_display_name(entity),
                "created_at": _iso_utc(entity.created_at),
                "updated_at": _iso_utc(entity.updated_at),
                "created_by": creator_names.get(entity.created_by_id, ""),
            }
            for column in columns[3:-3]:
                if column.startswith("sources."):
                    value = (data.get("sources") or {}).get(
                        column.removeprefix("sources.")
                    )
                else:
                    value = _nested_value(data, column)
                if column == "notes" and isinstance(value, str):
                    value = html_to_plain_text(value)
                row[column] = _csv_value(value)
            writer.writerow(row)

        return b"\xef\xbb\xbf" + output.getvalue().encode("utf-8")

    def write_entity_json(self, entities: list[models.Entity]) -> bytes:
        """Serialize the raw entity representation with creator usernames."""
        creator_names = self._creator_names(entities)
        records = [
            {
                "id": entity.id,
                "case_id": entity.case_id,
                "entity_type": entity.entity_type,
                "data": entity.data,
                "created_at": _iso_utc(entity.created_at),
                "updated_at": _iso_utc(entity.updated_at),
                "created_by_id": entity.created_by_id,
                "created_by": creator_names.get(entity.created_by_id, ""),
            }
            for entity in entities
        ]
        return json.dumps(records, ensure_ascii=False).encode("utf-8")

    def _get_entities(
        self,
        case_id: int,
        entity_types: list[str] | None,
        search: str | None,
    ) -> list[models.Entity]:
        query = select(models.Entity).where(models.Entity.case_id == case_id)
        if entity_types:
            query = query.where(col(models.Entity.entity_type).in_(entity_types))
        entities = list(self.db.exec(query.order_by(col(models.Entity.id))))

        if search:
            search_term = search.casefold()
            entities = [
                entity
                for entity in entities
                if search_term in entity_display_name(entity).casefold()
                or search_term in str(entity.data.get("description") or "").casefold()
            ]
        return entities

    def _entity_csv_columns(
        self,
        entities: list[models.Entity],
        empty_schema_types: list[str] | None,
    ) -> list[str]:
        exported_types = {entity.entity_type for entity in entities}
        if not exported_types:
            exported_types = set(empty_schema_types or ENTITY_EXPORT_SCHEMAS)
        data_columns: list[str] = []
        for entity_type, schema in ENTITY_EXPORT_SCHEMAS.items():
            if entity_type not in exported_types:
                continue
            for column in _schema_columns(schema):
                if column not in data_columns:
                    data_columns.append(column)

        source_columns = sorted(
            {
                f"sources.{key}"
                for entity in entities
                for key in (entity.data.get("sources") or {})
            }
        )
        return [
            "id",
            "entity_type",
            "display_name",
            *data_columns,
            *source_columns,
            "created_at",
            "updated_at",
            "created_by",
        ]

    def _creator_names(self, entities: list[models.Entity]) -> dict[int, str]:
        creator_ids = {entity.created_by_id for entity in entities}
        if not creator_ids:
            return {}
        users = self.db.exec(
            select(models.User).where(col(models.User.id).in_(creator_ids))
        )
        return {user.id: user.username for user in users if user.id is not None}


def filesystem_safe_name(value: str) -> str:
    """Return a conservative ASCII filename segment."""
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("._-")
    return safe_name or "case"


def entity_display_name(entity: models.Entity) -> str:
    """Return the entity name displayed in export rows and matched by search."""
    data = entity.data
    if entity.entity_type == "person":
        return " ".join(
            part for part in (data.get("first_name"), data.get("last_name")) if part
        )
    if entity.entity_type == "company":
        return str(data.get("name") or "")
    if entity.entity_type == "domain":
        return str(data.get("domain") or "")
    if entity.entity_type == "ip_address":
        return str(data.get("ip_address") or "")
    if entity.entity_type == "vehicle":
        return " ".join(
            str(part)
            for part in (data.get("year"), data.get("make"), data.get("model"))
            if part not in (None, "")
        )
    if entity.entity_type == "network_assets":
        assets = data.get("domains") or data.get("subdomains") or []
        return str(assets[0]) if assets else ""
    return ""


def html_to_plain_text(value: str) -> str:
    """Convert stored rich-text notes to readable lines."""
    soup = BeautifulSoup(value, "html.parser")
    for line_break in soup.find_all("br"):
        line_break.replace_with("\n")
    for block in soup.find_all(
        [
            "address",
            "article",
            "blockquote",
            "div",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "li",
            "p",
            "pre",
        ]
    ):
        block.append("\n")
    return "\n".join(
        line.strip() for line in soup.get_text().splitlines() if line.strip()
    )


def _schema_columns(schema: type[BaseModel], prefix: str = "") -> list[str]:
    columns: list[str] = []
    for field_name, field in schema.model_fields.items():
        if field_name == "sources":
            continue
        exported_name = field.alias or field_name
        column = f"{prefix}.{exported_name}" if prefix else exported_name
        nested_schema = _nested_schema(field.annotation)
        if nested_schema is None:
            columns.append(column)
        else:
            columns.extend(_schema_columns(nested_schema, column))
    return columns


def _nested_schema(annotation: Any) -> type[BaseModel] | None:
    candidates = (
        get_args(annotation)
        if get_origin(annotation) in (Union, UnionType)
        else (annotation,)
    )
    for candidate in candidates:
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            return candidate
    return None


_STORED_KEY_FALLBACKS = {
    "partner/spouse": "partner_spouse",
    "Affiliated Companies": "affiliated_companies",
    "Parent Company": "parent_company",
}


def _nested_value(data: dict[str, Any], column: str) -> Any:
    value: Any = data
    for key in column.split("."):
        if not isinstance(value, dict):
            return None
        if key in value:
            value = value[key]
        elif key in _STORED_KEY_FALLBACKS:
            value = value.get(_STORED_KEY_FALLBACKS[key])
        else:
            return None
    return value


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            return "; ".join(str(item) for item in value)
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _optional_iso_utc(value: datetime | None) -> str | None:
    return _iso_utc(value) if value is not None else None


class _HuntExecutionPDF(FPDF):
    def __init__(self, exported_at: str):
        super().__init__()
        self.exported_at = exported_at

    def footer(self) -> None:
        self.set_y(-13)
        self.set_font("DejaVu", size=8)
        self.set_text_color(90, 90, 90)
        self.cell(
            0,
            5,
            text=f"Exported {self.exported_at}    Page {self.page_no()}",
            align="C",
        )


def _pdf_heading(pdf: FPDF, text: str) -> None:
    pdf.ln(3)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("DejaVu", size=14)
    _pdf_text(pdf, text, line_height=8)


def _pdf_text(pdf: FPDF, text: Any, line_height: float = 5, fill: bool = False) -> None:
    pdf.multi_cell(
        0,
        line_height,
        text=str(text),
        fill=fill,
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
        wrapmode=WrapMode.CHAR,
        padding=1 if fill else 0,
    )


def _pdf_key_value_table(pdf: FPDF, rows: list[tuple[str, str]]) -> None:
    for label, value in rows:
        pdf.set_font("DejaVu", size=9)
        pdf.set_fill_color(235, 238, 242)
        pdf.cell(42, 6, text=str(label), border=1, fill=True)
        pdf.multi_cell(
            0,
            6,
            text=str(value),
            border=1,
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
            wrapmode=WrapMode.CHAR,
        )


def _readable_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _duration_text(start: str | None, end: str | None) -> str:
    if not start or not end:
        return "Not available"
    duration = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    total_seconds = max(0, int(duration.total_seconds()))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _truncate_utf8(value: str, max_bytes: int) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= max_bytes:
        return value, False
    return encoded[:max_bytes].decode("utf-8", errors="ignore"), True


def _evidence_references(context_data: Any) -> list[tuple[str, str]]:
    if not isinstance(context_data, dict):
        return []
    references = context_data.get("evidence_refs")
    if not isinstance(references, list):
        return []
    results: list[tuple[str, str]] = []
    for reference in references:
        if isinstance(reference, dict):
            results.append(
                (
                    str(reference.get("title") or reference.get("id") or "Evidence"),
                    str(reference.get("folder_path") or ""),
                )
            )
        else:
            results.append((str(reference), ""))
    return results
