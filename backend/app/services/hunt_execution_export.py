"""Typed, pure rendering for hunt execution JSON and PDF exports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import WrapMode, XPos, YPos
from pydantic import BaseModel

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
HUNT_OUTPUT_LIMIT_BYTES = 32 * 1024
HUNT_OUTPUT_TRUNCATION_NOTICE = (
    "[Output truncated. Full output is available in the JSON export.]"
)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


class HuntExecutionExportFormat(StrEnum):
    """Supported hunt execution export representations."""

    PDF = "pdf"
    JSON = "json"


class HuntDetailsSnapshot(BaseModel):
    id: int
    name: str
    display_name: str
    description: str
    category: str
    version: str
    is_active: bool
    initial_parameters: dict[str, Any]
    step_count: int
    created_at: datetime
    updated_at: datetime


class HuntStepSnapshot(BaseModel):
    id: int
    execution_id: int
    step_id: str
    plugin_name: str
    status: str
    parameters: dict[str, Any]
    output: dict[str, Any] | None
    error_details: str | None
    started_at: datetime | None
    completed_at: datetime | None


class HuntCaseSnapshot(BaseModel):
    id: int
    title: str | None
    case_number: str


class HuntCreatorSnapshot(BaseModel):
    id: int
    email: str
    username: str


class HuntExecutionSnapshot(BaseModel):
    """Complete, immutable-by-convention input to hunt export rendering."""

    id: int
    hunt_id: int
    case_id: int
    status: str
    progress: float
    initial_parameters: dict[str, Any]
    context_data: dict[str, Any] | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    created_by_id: int
    hunt: HuntDetailsSnapshot
    steps: list[HuntStepSnapshot]
    case: HuntCaseSnapshot
    created_by: HuntCreatorSnapshot


@dataclass(frozen=True)
class RenderedHuntExecutionExport:
    content: bytes
    media_type: str


def render_hunt_execution(
    snapshot: HuntExecutionSnapshot,
    exported_at: datetime,
    export_format: HuntExecutionExportFormat,
) -> RenderedHuntExecutionExport:
    """Render a typed execution snapshot in the requested representation."""
    if export_format is HuntExecutionExportFormat.PDF:
        return RenderedHuntExecutionExport(
            content=_render_pdf(snapshot, exported_at),
            media_type="application/pdf",
        )
    return RenderedHuntExecutionExport(
        content=_render_json(snapshot, exported_at),
        media_type="application/json",
    )


def _render_json(snapshot: HuntExecutionSnapshot, exported_at: datetime) -> bytes:
    return json.dumps(
        {
            "execution": snapshot.model_dump(mode="python"),
            "timestamp": _iso_utc(exported_at),
            "export_version": "1.0",
        },
        ensure_ascii=False,
        default=_json_default,
    ).encode("utf-8")


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return _iso_utc(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _render_pdf(snapshot: HuntExecutionSnapshot, exported_at: datetime) -> bytes:
    pdf = _HuntExecutionPDF(_iso_utc(exported_at))
    pdf.add_font("DejaVu", fname=FONT_DIR / "DejaVuSans.ttf")
    pdf.add_font("DejaVuMono", fname=FONT_DIR / "DejaVuSansMono.ttf")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_title(f"{snapshot.hunt.display_name} - Execution #{snapshot.id}")
    pdf.add_page()

    pdf.set_font("DejaVu", size=18)
    _pdf_text(pdf, snapshot.hunt.display_name, line_height=9)
    pdf.set_font("DejaVu", size=13)
    _pdf_text(pdf, f"Execution #{snapshot.id}", line_height=7)
    pdf.ln(2)

    title_details = [
        ("Case", f"{snapshot.case.case_number} - {snapshot.case.title or ''}"),
        ("Status", snapshot.status),
        ("Progress", f"{snapshot.progress * 100:g}%"),
        ("Created by", snapshot.created_by.username),
        ("Created", _iso_utc(snapshot.created_at)),
        ("Started", _optional_iso_utc(snapshot.started_at) or "Not started"),
        ("Completed", _optional_iso_utc(snapshot.completed_at) or "Not completed"),
        ("Duration", _duration_text(snapshot.started_at, snapshot.completed_at)),
    ]
    _pdf_key_value_table(pdf, title_details)

    _pdf_heading(pdf, "Hunt")
    _pdf_key_value_table(pdf, [("Category", snapshot.hunt.category)])
    pdf.set_font("DejaVu", size=10)
    _pdf_text(pdf, snapshot.hunt.description)

    _pdf_heading(pdf, "Initial Parameters")
    if snapshot.initial_parameters:
        _pdf_key_value_table(
            pdf,
            [
                (str(key), _readable_value(value))
                for key, value in snapshot.initial_parameters.items()
            ],
        )
    else:
        _pdf_text(pdf, "No initial parameters")

    _pdf_heading(pdf, "Execution Steps")
    if not snapshot.steps:
        _pdf_text(pdf, "No steps recorded")
    for index, step in enumerate(snapshot.steps, start=1):
        _render_step(pdf, step, index)

    evidence_references = _evidence_references(snapshot.context_data)
    if evidence_references:
        _pdf_heading(pdf, "Evidence References")
        pdf.set_font("DejaVu", size=10)
        for title, folder_path in evidence_references:
            suffix = f" - {folder_path}" if folder_path else ""
            _pdf_text(pdf, f"• {title}{suffix}")

    return bytes(pdf.output())


def _render_step(pdf: FPDF, step: HuntStepSnapshot, index: int) -> None:
    pdf.set_font("DejaVu", size=12)
    _pdf_text(
        pdf,
        f"Step {index}: {step.step_id} ({step.plugin_name})",
        line_height=7,
    )
    _pdf_key_value_table(
        pdf,
        [
            ("Status", step.status),
            ("Started", _optional_iso_utc(step.started_at) or "Not started"),
            ("Completed", _optional_iso_utc(step.completed_at) or "Not completed"),
            ("Duration", _duration_text(step.started_at, step.completed_at)),
        ],
    )
    pdf.set_font("DejaVu", size=10)
    _pdf_text(pdf, "Parameters")
    if step.parameters:
        _pdf_key_value_table(
            pdf,
            [
                (str(key), _readable_value(value))
                for key, value in step.parameters.items()
            ],
        )
    else:
        _pdf_text(pdf, "No parameters")

    if step.error_details:
        pdf.set_text_color(160, 0, 0)
        _pdf_text(pdf, f"Error: {step.error_details}")
        pdf.set_text_color(0, 0, 0)

    pdf.set_font("DejaVu", size=10)
    _pdf_text(pdf, "Output")
    output_text = json.dumps(step.output, ensure_ascii=False, indent=2, default=str)
    output_text, truncated = _truncate_utf8(output_text, HUNT_OUTPUT_LIMIT_BYTES)
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


def _optional_iso_utc(value: datetime | None) -> str | None:
    return _iso_utc(value) if value is not None else None


def _duration_text(start: datetime | None, end: datetime | None) -> str:
    if start is None or end is None:
        return "Not available"
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    total_seconds = max(0, int((end - start).total_seconds()))
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
