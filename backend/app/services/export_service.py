"""Generate lossless, reusable exports for Owlculus case data."""

from __future__ import annotations

import csv
import io
import json
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import UnionType
from typing import Any, Union, cast, get_args, get_origin

from bs4 import BeautifulSoup
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.core import file_storage
from app.core.exceptions import ResourceNotFoundException
from app.core.logging import get_security_logger
from app.core.utils import get_utc_now
from app.database import models
from app.schemas.entity_schema import ENTITY_TYPE_SCHEMAS, NetworkAssets
from app.schemas.entity_schema import entity_display_name as entity_data_display_name
from app.services.case_access import CaseAccess
from app.services.hunt_execution_export import (
    HuntCaseSnapshot,
    HuntCreatorSnapshot,
    HuntDetailsSnapshot,
    HuntExecutionExportFormat,
    HuntExecutionSnapshot,
    HuntStepSnapshot,
    render_hunt_execution,
)


class _NetworkAssetsExportData(NetworkAssets):
    notes: str | None = None
    sources: dict[str, str] | None = None


ENTITY_EXPORT_SCHEMAS = cast(
    dict[str, type[BaseModel]],
    {
        "person": ENTITY_TYPE_SCHEMAS["person"],
        "company": ENTITY_TYPE_SCHEMAS["company"],
        "domain": ENTITY_TYPE_SCHEMAS["domain"],
        "ip_address": ENTITY_TYPE_SCHEMAS["ip_address"],
        "network_assets": _NetworkAssetsExportData,
        "vehicle": ENTITY_TYPE_SCHEMAS["vehicle"],
    },
)


@dataclass(frozen=True)
class ExportArtifact:
    """A complete in-memory download produced by an export writer."""

    content: bytes
    media_type: str
    filename: str


@dataclass(frozen=True)
class CaseBundleArtifact:
    """A temporary case archive ready to be streamed and removed."""

    path: Path
    filename: str


class EntityExportFormat(StrEnum):
    """Supported standalone entity export representations."""

    CSV = "csv"
    JSON = "json"


class ExportService:
    """Own export access checks, filtering, serialization, and audit logging."""

    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)

    def export_entities(
        self,
        case_id: int,
        current_user: models.User,
        export_format: EntityExportFormat,
        entity_types: list[str] | None = None,
        search: str | None = None,
    ) -> ExportArtifact:
        """Return every entity matching the supplied case-table filters."""
        case = self.case_access.readable(current_user, case_id)
        persisted_case_id = cast(int, case.id)
        entities = self._get_entities(persisted_case_id, entity_types, search)
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
            case_id=case.id,
            export_kind="entities",
            format=export_format.value,
            event_type="export_generated",
        ).info("Entity export generated")

        return ExportArtifact(
            content=content,
            media_type=media_type,
            filename=f"{safe_case_number}-entities-{export_date}.{export_format.value}",
        )

    def export_case_bundle(
        self, case_id: int, current_user: models.User
    ) -> CaseBundleArtifact:
        """Assemble a complete case snapshot in a temporary ZIP archive."""
        case = self.case_access.readable(current_user, case_id)
        persisted_case_id = cast(int, case.id)
        exported_at = get_utc_now()
        safe_case_number = filesystem_safe_name(case.case_number)
        root = f"{safe_case_number}/"
        export_logger = get_security_logger(
            user_id=current_user.id,
            requesting_user=current_user.username,
            case_id=case.id,
            export_kind="case",
            format="zip",
        )
        with tempfile.NamedTemporaryFile(
            prefix="owlculus-case-export-", suffix=".zip", delete=False
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        try:
            with zipfile.ZipFile(
                temporary_path,
                mode="w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                self._write_case_metadata(
                    archive, root, case, current_user, exported_at
                )
                if case.notes:
                    _write_zip_bytes(
                        archive,
                        f"{root}notes.html",
                        case.notes.encode("utf-8"),
                    )
                entities = self._get_entities(persisted_case_id, None, None)
                _write_zip_bytes(
                    archive,
                    f"{root}entities/entities.json",
                    self.write_entity_json(entities),
                )
                for entity_type in ENTITY_EXPORT_SCHEMAS:
                    typed_entities = [
                        entity
                        for entity in entities
                        if entity.entity_type == entity_type
                    ]
                    if typed_entities:
                        _write_zip_bytes(
                            archive,
                            f"{root}entities/{entity_type}.csv",
                            self.write_entity_csv(typed_entities),
                        )
                self._write_evidence(archive, root, persisted_case_id)
                tasks = list(
                    self.db.exec(
                        select(models.Task)
                        .where(models.Task.case_id == case.id)
                        .order_by(col(models.Task.id))
                    )
                )
                _write_zip_bytes(
                    archive,
                    f"{root}tasks/tasks.json",
                    self.write_task_json(tasks),
                )
                _write_zip_bytes(
                    archive,
                    f"{root}tasks/tasks.csv",
                    self.write_task_csv(tasks),
                )
                self._write_hunts(archive, root, case, exported_at)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            export_logger.bind(event_type="export_generation_failed").exception(
                "Case export failed"
            )
            raise

        export_logger.bind(event_type="export_generated").info("Case export generated")

        return CaseBundleArtifact(
            path=temporary_path,
            filename=(
                f"{safe_case_number}-export-{exported_at.date().isoformat()}.zip"
            ),
        )

    def _write_case_metadata(
        self,
        archive: zipfile.ZipFile,
        root: str,
        case: models.Case,
        current_user: models.User,
        exported_at: datetime,
    ) -> None:
        client = self.db.get(models.Client, case.client_id) if case.client_id else None
        assigned_users = list(
            self.db.exec(
                select(models.User, models.CaseUserLink.is_lead)
                .join(
                    models.CaseUserLink,
                    col(models.CaseUserLink.user_id) == models.User.id,
                )
                .where(models.CaseUserLink.case_id == case.id)
                .order_by(col(models.User.id))
            )
        )
        metadata = {
            "id": case.id,
            "case_number": case.case_number,
            "title": case.title,
            "status": case.status,
            "client": (
                {"id": client.id, "name": client.name} if client is not None else None
            ),
            "users": [
                {
                    "username": user.username,
                    "role": user.role,
                    "is_lead": is_lead,
                }
                for user, is_lead in assigned_users
            ],
            "created_at": _iso_utc(case.created_at),
            "updated_at": _iso_utc(case.updated_at),
            "exported_at": _iso_utc(exported_at),
            "exported_by": current_user.username,
        }
        _write_zip_json(archive, f"{root}case.json", metadata)

    def write_task_json(self, tasks: list[models.Task]) -> bytes:
        """Serialize case tasks with readable relationship names."""
        return json.dumps(
            self._task_records(tasks),
            ensure_ascii=False,
            default=_json_default,
        ).encode("utf-8")

    def write_task_csv(self, tasks: list[models.Task]) -> bytes:
        """Serialize case tasks using the stable task spreadsheet contract."""
        output = io.StringIO(newline="")
        writer = csv.DictWriter(
            output, fieldnames=TASK_CSV_COLUMNS, lineterminator="\r\n"
        )
        writer.writeheader()
        for record in self._task_records(tasks):
            writer.writerow(
                {
                    column: (
                        json.dumps(record[column], ensure_ascii=False)
                        if column == "custom_fields" and record[column] is not None
                        else record[column]
                    )
                    for column in TASK_CSV_COLUMNS
                }
            )
        return output.getvalue().encode("utf-8")

    def _write_evidence(
        self, archive: zipfile.ZipFile, root: str, case_id: int
    ) -> None:
        evidence_records = list(
            self.db.exec(
                select(models.Evidence)
                .where(models.Evidence.case_id == case_id)
                .order_by(col(models.Evidence.id))
            )
        )
        creator_names = self._usernames_by_id(
            {evidence.created_by_id for evidence in evidence_records}
        )
        manifest = []
        upload_root = file_storage.UPLOAD_DIR.resolve()

        for evidence in evidence_records:
            folder_path = _safe_archive_path(evidence.folder_path)
            evidence_root = f"{root}evidence/"
            destination_folder = (
                f"{evidence_root}{folder_path}/" if folder_path else evidence_root
            )
            file_name: str | None = None
            exported = True
            reason: str | None = None

            if evidence.is_folder:
                _write_zip_bytes(archive, destination_folder, b"")
            elif evidence.evidence_type == "text":
                file_name = f"{_safe_archive_component(evidence.title)}.txt"
                _write_zip_bytes(
                    archive,
                    f"{destination_folder}{file_name}",
                    (evidence.content or "").encode("utf-8"),
                )
            elif evidence.evidence_type == "file":
                file_name = PurePosixPath(
                    (evidence.content or "").replace("\\", "/")
                ).name or _safe_archive_component(evidence.title)
                source_path = (
                    file_storage.UPLOAD_DIR / (evidence.content or "")
                ).resolve()
                if not _is_stored_evidence_file(source_path, upload_root):
                    exported = False
                    reason = "File not found on disk"
                    get_security_logger(
                        case_id=case_id,
                        evidence_id=evidence.id,
                        file_path=str(source_path),
                        event_type="case_export_evidence_missing",
                    ).warning("Case export evidence file not found on disk")
                else:
                    archive.write(
                        source_path,
                        arcname=f"{destination_folder}{file_name}",
                        compress_type=zipfile.ZIP_STORED,
                    )
            else:
                exported = False
                reason = f"Unsupported evidence type: {evidence.evidence_type}"

            manifest_record = {
                "id": evidence.id,
                "title": evidence.title,
                "description": evidence.description,
                "category": evidence.category,
                "evidence_type": evidence.evidence_type,
                "folder_path": evidence.folder_path,
                "file_name": file_name,
                "file_hash": evidence.file_hash,
                "is_folder": evidence.is_folder,
                "parent_folder_id": evidence.parent_folder_id,
                "created_by": creator_names.get(evidence.created_by_id, ""),
                "created_at": _iso_utc(evidence.created_at),
                "updated_at": _iso_utc(evidence.updated_at),
                "exported": exported,
            }
            if reason is not None:
                manifest_record["reason"] = reason
            manifest.append(manifest_record)

        _write_zip_json(archive, f"{root}evidence/manifest.json", manifest)

    def _task_records(self, tasks: list[models.Task]) -> list[dict[str, Any]]:
        user_ids = {
            user_id
            for task in tasks
            for user_id in (
                task.assigned_to_id,
                task.assigned_by_id,
                task.completed_by_id,
            )
            if user_id is not None
        }
        usernames = self._usernames_by_id(user_ids)
        template_ids = {
            task.template_id for task in tasks if task.template_id is not None
        }
        templates = (
            {
                template.id: template.name
                for template in self.db.exec(
                    select(models.TaskTemplate).where(
                        col(models.TaskTemplate.id).in_(template_ids)
                    )
                )
            }
            if template_ids
            else {}
        )

        return [
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "status": task.status,
                "priority": task.priority,
                "assigned_to": (
                    usernames.get(task.assigned_to_id)
                    if task.assigned_to_id is not None
                    else None
                ),
                "assigned_by": usernames.get(task.assigned_by_id),
                "due_date": _optional_iso_utc(task.due_date),
                "completed_at": _optional_iso_utc(task.completed_at),
                "completed_by": (
                    usernames.get(task.completed_by_id)
                    if task.completed_by_id is not None
                    else None
                ),
                "template": templates.get(task.template_id),
                "custom_fields": task.custom_fields,
                "created_at": _iso_utc(task.created_at),
                "updated_at": _iso_utc(task.updated_at),
            }
            for task in tasks
        ]

    def _write_hunts(
        self,
        archive: zipfile.ZipFile,
        root: str,
        case: models.Case,
        exported_at: datetime,
    ) -> None:
        executions = list(
            self.db.exec(
                select(models.HuntExecution)
                .where(models.HuntExecution.case_id == case.id)
                .order_by(col(models.HuntExecution.created_at).desc())
            )
        )
        snapshots = [
            self._hunt_execution_snapshot(execution, case) for execution in executions
        ]
        _write_zip_json(
            archive,
            f"{root}hunts/executions.json",
            [
                {
                    "id": snapshot.id,
                    "hunt_id": snapshot.hunt_id,
                    "case_id": snapshot.case_id,
                    "status": snapshot.status,
                    "progress": snapshot.progress,
                    "initial_parameters": snapshot.initial_parameters,
                    "started_at": snapshot.started_at,
                    "completed_at": snapshot.completed_at,
                    "created_at": snapshot.created_at,
                    "created_by_id": snapshot.created_by_id,
                    "hunt_display_name": snapshot.hunt.display_name,
                    "hunt_category": snapshot.hunt.category,
                }
                for snapshot in snapshots
            ],
        )
        for snapshot in snapshots:
            hunt_name = filesystem_safe_name(snapshot.hunt.name)
            execution_root = f"{root}hunts/{snapshot.id}-{hunt_name}/"
            for export_format in (
                HuntExecutionExportFormat.JSON,
                HuntExecutionExportFormat.PDF,
            ):
                rendered = render_hunt_execution(snapshot, exported_at, export_format)
                _write_zip_bytes(
                    archive,
                    f"{execution_root}execution.{export_format.value}",
                    rendered.content,
                )

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

        case = self.case_access.readable(current_user, execution.case_id)
        snapshot = self._hunt_execution_snapshot(execution, case)
        hunt_name = filesystem_safe_name(snapshot.hunt.name)
        exported_at = get_utc_now()
        export_logger = get_security_logger(
            user_id=current_user.id,
            requesting_user=current_user.username,
            case_id=case.id,
            export_kind="hunt_execution",
            format=export_format.value,
        )
        try:
            rendered = render_hunt_execution(snapshot, exported_at, export_format)
        except Exception:
            export_logger.bind(event_type="export_generation_failed").exception(
                "Hunt execution export failed"
            )
            raise

        export_logger.bind(
            event_type="export_generated",
        ).info("Hunt execution export generated")

        return ExportArtifact(
            content=rendered.content,
            media_type=rendered.media_type,
            filename=(
                f"hunt-execution-{execution_id}-{hunt_name}.{export_format.value}"
            ),
        )

    def _hunt_execution_snapshot(
        self, execution: models.HuntExecution, case: models.Case
    ) -> HuntExecutionSnapshot:
        hunt = self.db.get(models.Hunt, execution.hunt_id)
        creator = self.db.get(models.User, execution.created_by_id)
        steps = list(
            self.db.exec(
                select(models.HuntStep)
                .where(models.HuntStep.execution_id == execution.id)
                .order_by(col(models.HuntStep.id))
            )
        )
        if hunt is None or creator is None:
            raise ResourceNotFoundException("Hunt execution related data not found")

        return HuntExecutionSnapshot(
            id=cast(int, execution.id),
            hunt_id=execution.hunt_id,
            case_id=execution.case_id,
            status=execution.status,
            progress=execution.progress,
            initial_parameters=execution.initial_parameters,
            context_data=execution.context_data,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            created_at=execution.created_at,
            created_by_id=execution.created_by_id,
            hunt=HuntDetailsSnapshot(
                id=cast(int, hunt.id),
                name=hunt.name,
                display_name=hunt.display_name,
                description=hunt.description,
                category=hunt.category,
                version=hunt.version,
                is_active=hunt.is_active,
                initial_parameters=hunt.definition_json.get("initial_parameters", {}),
                step_count=len(hunt.definition_json.get("steps", [])),
                created_at=hunt.created_at,
                updated_at=hunt.updated_at,
            ),
            steps=[
                HuntStepSnapshot(
                    id=cast(int, step.id),
                    execution_id=step.execution_id,
                    step_id=step.step_id,
                    plugin_name=step.plugin_name,
                    status=step.status,
                    parameters=step.parameters,
                    output=step.output,
                    error_details=step.error_details,
                    started_at=step.started_at,
                    completed_at=step.completed_at,
                )
                for step in steps
            ],
            case=HuntCaseSnapshot(
                id=cast(int, case.id),
                title=case.title,
                case_number=case.case_number,
            ),
            created_by=HuntCreatorSnapshot(
                id=cast(int, creator.id),
                email=str(creator.email),
                username=creator.username,
            ),
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
        return self._usernames_by_id({entity.created_by_id for entity in entities})

    def _usernames_by_id(self, user_ids: set[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        users = self.db.exec(
            select(models.User).where(col(models.User.id).in_(user_ids))
        )
        return {user.id: user.username for user in users if user.id is not None}


def filesystem_safe_name(value: str) -> str:
    """Return a conservative ASCII filename segment."""
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("._-")
    return safe_name or "case"


def entity_display_name(entity: models.Entity) -> str:
    """Return the entity name displayed in export rows and matched by search."""
    return entity_data_display_name(entity.entity_type, entity.data)


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


TASK_CSV_COLUMNS = [
    "id",
    "title",
    "description",
    "status",
    "priority",
    "assigned_to",
    "assigned_by",
    "due_date",
    "completed_at",
    "completed_by",
    "template",
    "custom_fields",
    "created_at",
    "updated_at",
]


def _write_zip_json(archive: zipfile.ZipFile, member_name: str, value: Any) -> None:
    _write_zip_bytes(
        archive,
        member_name,
        json.dumps(value, ensure_ascii=False, default=_json_default).encode("utf-8"),
    )


def _write_zip_bytes(
    archive: zipfile.ZipFile, member_name: str, content: bytes
) -> None:
    archive.writestr(member_name, content, compress_type=zipfile.ZIP_DEFLATED)


def _optional_iso_utc(value: datetime | None) -> str | None:
    return _iso_utc(value) if value is not None else None


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return _iso_utc(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _safe_archive_path(value: str | None) -> str:
    if not value:
        return ""
    return "/".join(
        _safe_archive_component(part)
        for part in value.replace("\\", "/").split("/")
        if part not in ("", ".", "..")
    )


def _safe_archive_component(value: str) -> str:
    component = "".join(
        "-" if character in "/\\" or ord(character) < 32 else character
        for character in value
    ).strip()
    return component if component not in ("", ".", "..") else "evidence"


def _is_stored_evidence_file(source_path: Path, upload_root: Path) -> bool:
    try:
        source_path.relative_to(upload_root)
    except ValueError:
        return False
    return source_path.is_file()
