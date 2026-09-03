"""Generate lossless, reusable exports for Owlculus case data."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from types import UnionType
from typing import Any, Union, get_args, get_origin

from bs4 import BeautifulSoup
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.core.dependencies import check_case_access
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


@dataclass(frozen=True)
class ExportArtifact:
    """A complete in-memory download produced by an export writer."""

    content: bytes
    media_type: str
    filename: str


class ExportService:
    """Own export access checks, filtering, serialization, and audit logging."""

    def __init__(self, db: Session):
        self.db = db

    def export_entities(
        self,
        case_id: int,
        current_user: models.User,
        export_format: str,
        entity_types: list[str] | None = None,
        search: str | None = None,
    ) -> ExportArtifact:
        """Return every entity matching the supplied case-table filters."""
        case = check_case_access(self.db, case_id, current_user)
        entities = self._get_entities(case_id, entity_types, search)
        safe_case_number = filesystem_safe_name(case.case_number)
        export_date = get_utc_now().date().isoformat()

        if export_format == "json":
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
            format=export_format,
            event_type="export_generated",
        ).info("Entity export generated")

        return ExportArtifact(
            content=content,
            media_type=media_type,
            filename=f"{safe_case_number}-entities-{export_date}.{export_format}",
        )

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
