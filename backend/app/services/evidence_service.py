"""
Evidence management service for Owlculus OSINT case file handling and storage.

This module handles all evidence-related operations including file uploads,
folder management, evidence validation, and secure file access. Provides
comprehensive evidence lifecycle management with file hashing, content viewing,
template-based folder structures, and role-based access control for OSINT investigations.
"""

from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from sqlmodel import Session, select

from app.core.exceptions import (
    AuthorizationException,
    DomainException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.file_storage import (
    create_folder,
    delete_file,
    delete_folder,
    evidence_file_path,
    normalize_folder_path,
    save_upload_file,
)
from app.core.logging import get_security_logger
from app.core.utils import get_utc_now
from app.database import models
from app.database.db_utils import transaction
from app.schemas import evidence_schema as schemas
from app.services.case_access import CaseAccess


class EvidenceService:
    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)

    def can_read(self, evidence: models.Evidence, user: models.User) -> bool:
        """Shared listing/export boundary, including protected report metadata."""
        try:
            self.require_read(evidence, user)
        except (AuthorizationException, ResourceNotFoundException):
            return False
        return True

    def require_read(self, evidence: models.Evidence, user: models.User) -> None:
        """Authorize immutable reports against every Case represented in them."""
        from app.database.correlation_provenance import report_provenance

        self.case_access.readable(user, evidence.case_id)
        provenance = report_provenance(self.db, evidence)
        if provenance is None or self.case_access.is_admin(user):
            return
        readable = set(self.case_access.readable_case_ids(user))
        if not provenance.case_ids or not set(provenance.case_ids) <= readable:
            raise AuthorizationException("Not authorized to access this evidence")

    def _response(self, evidence: models.Evidence) -> models.Evidence:
        parent_id = self.case_access.eligible_evidence_parent_id(
            evidence.case_id, evidence.parent_folder_id
        )
        if parent_id != evidence.parent_folder_id:
            # Keep the stored path and contents usable without expanding a foreign parent.
            return evidence.model_copy(update={"parent_folder_id": parent_id})
        return evidence

    @staticmethod
    def _fail(log: Any, reason: str, error: DomainException, **fields: Any):
        """Log a rejected operation on its ``*_failed`` logger and return the error."""
        log.bind(failure_reason=reason, **fields).warning(str(error))
        return error

    def _stored_file(self, evidence: models.Evidence, failed: Any) -> Path:
        try:
            return evidence_file_path(evidence.case_id, evidence.content or "")
        except ValueError:
            raise self._fail(
                failed,
                "file_not_found",
                ResourceNotFoundException("File not found"),
                file_path=evidence.content,
            ) from None

    def _folder(
        self,
        case_id: int,
        title: str,
        description: str | None,
        folder_path: str,
        parent_folder_id: int | None,
        current_user: models.User,
    ) -> models.Evidence:
        return models.Evidence(
            case_id=case_id,
            title=title,
            description=description,
            evidence_type="folder",
            category="Other",
            content="",
            folder_path=folder_path,
            is_folder=True,
            parent_folder_id=parent_folder_id,
            created_by_id=current_user.id,
            created_at=get_utc_now(),
            updated_at=get_utc_now(),
        )

    async def create_evidence(
        self,
        evidence: schemas.EvidenceCreate,
        current_user: models.User,
        file: Any | None = None,
        *,
        artifact_id: str | None = None,
        correlation_case_ids: tuple[int, ...] | None = None,
    ) -> models.Evidence:
        self.case_access.writable(current_user, evidence.case_id)
        self.case_access.evidence_parent(evidence.case_id, evidence.parent_folder_id)
        evidence_logger = get_security_logger(
            user_id=current_user.id,
            case_id=evidence.case_id,
            action="create_evidence",
            evidence_type=evidence.evidence_type,
            event_type="evidence_creation_attempt",
        )
        failed = evidence_logger.bind(event_type="evidence_creation_failed")

        saved_path = None
        if evidence.evidence_type == "file" and not evidence.is_folder:
            if not self.db.exec(
                select(models.Evidence).where(
                    models.Evidence.case_id == evidence.case_id,
                    models.Evidence.is_folder == True,
                )
            ).first():
                raise self._fail(
                    failed,
                    "no_folders_exist",
                    ValidationException(
                        "Cannot upload files without any folders. Create a folder first to organize evidence."
                    ),
                )
            if not file:
                raise self._fail(
                    failed,
                    "file_required",
                    ValidationException("File is required for file-type evidence"),
                )
            saved_path, evidence.file_hash = await save_upload_file(
                upload_file=file,
                case_id=evidence.case_id,
                folder_path=evidence.folder_path,
                artifact_id=artifact_id,
            )
            evidence.content = saved_path
            # Update title to reflect actual saved filename after duplicate handling
            if artifact_id is None:
                evidence.title = saved_path.split("/")[-1]

        db_evidence = models.Evidence(
            case_id=evidence.case_id,
            title=evidence.title,
            description=evidence.description,
            evidence_type=evidence.evidence_type,
            category=evidence.category,
            content=evidence.content,
            file_hash=evidence.file_hash,
            folder_path=evidence.folder_path,
            is_folder=evidence.is_folder,
            parent_folder_id=evidence.parent_folder_id,
            created_by_id=current_user.id,
            created_at=get_utc_now(),
            updated_at=get_utc_now(),
        )

        try:
            with transaction(self.db):
                self.db.add(db_evidence)
                if correlation_case_ids is not None:
                    self.db.flush()
                    self.db.add(
                        models.CorrelationEvidence(
                            evidence_id=cast(int, db_evidence.id),
                            case_ids=(
                                sorted({evidence.case_id, *correlation_case_ids})
                                if correlation_case_ids
                                else None
                            ),
                        )
                    )
            self.db.refresh(db_evidence)
        except Exception:
            # Don't orphan the uploaded file; execution artifacts are reconciled.
            if saved_path and artifact_id is None:
                with suppress(Exception):
                    await delete_file(saved_path)
            raise

        evidence_logger.bind(
            evidence_id=db_evidence.id,
            evidence_title=db_evidence.title,
            evidence_category=db_evidence.category,
            event_type="evidence_creation_success",
        ).info("Evidence created successfully")

        return self._response(db_evidence)

    async def get_case_evidence(
        self,
        case_id: int,
        current_user: models.User,
        skip: int = 0,
        limit: int | None = 100,
    ) -> list[models.Evidence]:
        self.case_access.readable(current_user, case_id)

        query = (
            select(models.Evidence)
            .where(models.Evidence.case_id == case_id)
            .offset(skip)
            .limit(limit)
        )
        return [
            self._response(evidence)
            for evidence in self.db.exec(query)
            if self.can_read(evidence, current_user)
        ]

    async def get_evidence(
        self, evidence_id: int, current_user: models.User
    ) -> models.Evidence:
        evidence = self.db.get(models.Evidence, evidence_id)
        if not evidence:
            raise ResourceNotFoundException("Evidence not found")

        self.require_read(evidence, current_user)

        return self._response(evidence)

    def update_evidence(
        self,
        evidence_id: int,
        evidence_update: schemas.EvidenceUpdate,
        current_user: models.User,
    ) -> models.Evidence:
        evidence_logger = get_security_logger(
            user_id=current_user.id,
            evidence_id=evidence_id,
            action="update_evidence",
            event_type="evidence_update_attempt",
        )
        failed = evidence_logger.bind(event_type="evidence_update_failed")

        db_evidence = self.db.get(models.Evidence, evidence_id)
        if not db_evidence:
            raise self._fail(
                failed,
                "evidence_not_found",
                ResourceNotFoundException("Evidence not found"),
            )

        self.require_read(db_evidence, current_user)
        self.case_access.writable(current_user, db_evidence.case_id)
        self.case_access.evidence_parent(
            db_evidence.case_id, evidence_update.parent_folder_id
        )

        from app.database.correlation_provenance import report_provenance

        provenance = report_provenance(self.db, db_evidence)
        if provenance is not None:
            self.db.merge(provenance)

        if evidence_update.title is not None:
            db_evidence.title = evidence_update.title
        if evidence_update.description is not None:
            db_evidence.description = evidence_update.description
        if evidence_update.content is not None:
            if db_evidence.evidence_type == "file":
                raise self._fail(
                    failed,
                    "file_content_not_updatable",
                    ValidationException("Cannot update content of file-type evidence"),
                )
            db_evidence.content = evidence_update.content
        if evidence_update.parent_folder_id is not None:
            db_evidence.parent_folder_id = evidence_update.parent_folder_id

        db_evidence.updated_at = get_utc_now()

        with transaction(self.db):
            self.db.add(db_evidence)
        self.db.refresh(db_evidence)

        evidence_logger.bind(
            case_id=db_evidence.case_id,
            evidence_title=db_evidence.title,
            event_type="evidence_update_success",
        ).info("Evidence updated successfully")

        return self._response(db_evidence)

    async def delete_evidence(
        self, evidence_id: int, current_user: models.User
    ) -> models.Evidence | None:
        evidence_logger = get_security_logger(
            user_id=current_user.id,
            evidence_id=evidence_id,
            action="delete_evidence",
            event_type="evidence_deletion_attempt",
        )
        failed = evidence_logger.bind(event_type="evidence_deletion_failed")

        evidence = self.db.get(models.Evidence, evidence_id)
        if not evidence:
            # Handle race condition where evidence may already be deleted in bulk operations
            evidence_logger.bind(
                event_type="evidence_already_deleted",
            ).info("Evidence already deleted or not found")
            return None

        self.require_read(evidence, current_user)
        self.case_access.writable(current_user, evidence.case_id)

        if evidence.evidence_type == "file" and evidence.content:
            try:
                await delete_file(evidence.content)
            except Exception as e:
                raise self._fail(
                    failed,
                    "file_deletion_error",
                    DomainException("Error deleting file"),
                ) from e

        with transaction(self.db):
            provenance = self.db.get(models.CorrelationEvidence, evidence.id)
            if provenance is not None:
                self.db.delete(provenance)
            self.db.delete(evidence)

        evidence_logger.bind(
            case_id=evidence.case_id,
            evidence_title=evidence.title,
            evidence_type=evidence.evidence_type,
            event_type="evidence_deletion_success",
        ).info("Evidence deleted successfully")

        return evidence

    async def download_evidence(
        self,
        evidence_id: int,
        current_user: models.User,
    ) -> Path:
        evidence_logger = get_security_logger(
            user_id=current_user.id,
            evidence_id=evidence_id,
            action="download_evidence",
            event_type="evidence_download_attempt",
        )
        failed = evidence_logger.bind(event_type="evidence_download_failed")

        evidence = await self.get_evidence(evidence_id, current_user)
        if evidence.evidence_type != "file":
            raise self._fail(
                failed,
                "unsupported_evidence_type",
                ValidationException("Evidence type does not support downloading"),
                evidence_type=evidence.evidence_type,
            )

        file_path = self._stored_file(evidence, failed)
        evidence_logger.bind(
            case_id=evidence.case_id,
            evidence_title=evidence.title,
            filename=file_path.name,
            event_type="evidence_download_success",
        ).info("Evidence downloaded successfully")

        return file_path

    async def get_evidence_content(
        self,
        evidence_id: int,
        current_user: models.User,
    ) -> dict:
        """Get text content of evidence file for viewing."""
        evidence_logger = get_security_logger(
            user_id=current_user.id,
            evidence_id=evidence_id,
            action="get_evidence_content",
            event_type="evidence_content_view_attempt",
        )
        failed = evidence_logger.bind(event_type="evidence_content_view_failed")

        evidence = await self.get_evidence(evidence_id, current_user)

        if evidence.is_folder:
            raise self._fail(
                failed,
                "is_folder",
                ValidationException("Cannot view content of folders"),
            )

        if evidence.evidence_type != "file":
            raise self._fail(
                failed,
                "not_file_type",
                ValidationException("Evidence type does not support content viewing"),
                evidence_type=evidence.evidence_type,
            )

        import chardet

        file_path = self._stored_file(evidence, failed)

        # Whole file is read into memory below, so cap its size.
        file_size = file_path.stat().st_size
        max_size = 1024 * 1024
        if file_size > max_size:
            raise self._fail(
                failed,
                "file_too_large",
                ValidationException(
                    f"File too large for viewing. Maximum size: {max_size // 1024}KB"
                ),
                file_size=file_size,
                max_size=max_size,
            )

        viewable_extensions = {
            ".txt",
            ".log",
            ".csv",
            ".json",
            ".md",
            ".yaml",
            ".yml",
            ".xml",
            ".html",
            ".css",
            ".js",
            ".py",
            ".sql",
            ".conf",
            ".ini",
            ".cfg",
        }
        file_extension = file_path.suffix.lower()

        if file_extension not in viewable_extensions:
            raise self._fail(
                failed,
                "unsupported_file_type",
                ValidationException(
                    f"File type '{file_extension}' is not supported for text viewing"
                ),
                file_extension=file_extension,
            )

        raw_content = file_path.read_bytes()

        encoding_result = chardet.detect(raw_content)
        encoding = encoding_result.get("encoding") or "utf-8"
        confidence = encoding_result.get("confidence", 0)

        try:
            content = raw_content.decode(encoding)
        except UnicodeDecodeError:
            content = raw_content.decode("utf-8", errors="replace")
            encoding = "utf-8 (with errors replaced)"
            confidence = 0

        evidence_logger.bind(
            case_id=evidence.case_id,
            evidence_title=evidence.title,
            file_size=file_size,
            encoding_detected=encoding,
            encoding_confidence=confidence,
            event_type="evidence_content_view_success",
        ).info("Evidence content viewed successfully")

        return {
            "success": True,
            "content": content,
            "file_info": {
                "filename": evidence.title,
                "file_extension": file_extension,
                "file_size": file_size,
                "encoding": encoding,
                "encoding_confidence": confidence,
                "line_count": len(content.splitlines()),
                "char_count": len(content),
            },
        }

    async def create_folder(
        self,
        folder_data: schemas.FolderCreate,
        current_user: models.User,
    ) -> models.Evidence:
        """Create a new folder in the case directory."""
        self.case_access.writable(current_user, folder_data.case_id)
        parent_folder = self.case_access.evidence_parent(
            folder_data.case_id, folder_data.parent_folder_id
        )
        folder_logger = get_security_logger(
            user_id=current_user.id,
            case_id=folder_data.case_id,
            action="create_folder",
            folder_title=folder_data.title,
            event_type="folder_creation_attempt",
        )

        folder_path = (
            f"{parent_folder.folder_path}/{folder_data.title}"
            if parent_folder is not None and parent_folder.folder_path
            else folder_data.title
        )
        create_folder(folder_data.case_id, folder_path)

        db_folder = self._folder(
            folder_data.case_id,
            folder_data.title,
            folder_data.description,
            folder_path,
            folder_data.parent_folder_id,
            current_user,
        )
        try:
            with transaction(self.db):
                self.db.add(db_folder)
            self.db.refresh(db_folder)
        except Exception:
            # Don't orphan the physical folder when its record fails.
            with suppress(Exception):
                delete_folder(folder_data.case_id, folder_path)
            raise

        folder_logger.bind(
            folder_id=db_folder.id,
            folder_path=folder_path,
            event_type="folder_creation_success",
        ).info("Folder created successfully")

        return self._response(db_folder)

    async def update_folder(
        self,
        folder_id: int,
        folder_update: schemas.FolderUpdate,
        current_user: models.User,
    ) -> models.Evidence:
        """Update a folder."""
        folder_logger = get_security_logger(
            user_id=current_user.id,
            folder_id=folder_id,
            action="update_folder",
            event_type="folder_update_attempt",
        )
        failed = folder_logger.bind(event_type="folder_update_failed")

        db_folder = self.db.get(models.Evidence, folder_id)
        if not db_folder or not db_folder.is_folder:
            raise self._fail(
                failed,
                "folder_not_found",
                ResourceNotFoundException("Folder not found"),
            )

        self.case_access.writable(current_user, db_folder.case_id)
        self.case_access.evidence_parent(
            db_folder.case_id, folder_update.parent_folder_id
        )

        if folder_update.title is not None:
            db_folder.title = folder_update.title
        if folder_update.description is not None:
            db_folder.description = folder_update.description
        if folder_update.parent_folder_id is not None:
            db_folder.parent_folder_id = folder_update.parent_folder_id

        db_folder.updated_at = get_utc_now()

        with transaction(self.db):
            self.db.add(db_folder)
        self.db.refresh(db_folder)

        folder_logger.bind(
            case_id=db_folder.case_id,
            folder_title=db_folder.title,
            event_type="folder_update_success",
        ).info("Folder updated successfully")

        return self._response(db_folder)

    async def delete_folder(
        self, folder_id: int, current_user: models.User
    ) -> models.Evidence | None:
        """Delete a folder and all its contents."""
        folder_logger = get_security_logger(
            user_id=current_user.id,
            folder_id=folder_id,
            action="delete_folder",
            event_type="folder_deletion_attempt",
        )
        failed = folder_logger.bind(event_type="folder_deletion_failed")

        db_folder = self.db.get(models.Evidence, folder_id)
        if not db_folder:
            # Handle race condition in bulk delete operations
            folder_logger.bind(
                event_type="folder_already_deleted",
            ).info("Folder already deleted or not found")
            return None

        if not db_folder.is_folder:
            raise self._fail(
                failed, "not_a_folder", ResourceNotFoundException("Folder not found")
            )

        self.case_access.writable(current_user, db_folder.case_id)

        # Storage normalizes paths, so aliases must share a deletion scope.
        folder_path = normalize_folder_path(db_folder.folder_path or "")
        affected_evidence = [db_folder]
        if folder_path:
            case_evidence = self.db.exec(
                select(models.Evidence).where(
                    models.Evidence.case_id == db_folder.case_id,
                    models.Evidence.id != db_folder.id,
                )
            ).all()
            for evidence in case_evidence:
                evidence_path = normalize_folder_path(evidence.folder_path or "")
                if evidence_path == folder_path or evidence_path.startswith(
                    f"{folder_path}/"
                ):
                    affected_evidence.append(evidence)

        # Authorize the entire deletion set before touching files or records.
        for evidence in affected_evidence:
            self.require_read(evidence, current_user)

        if db_folder.folder_path:
            try:
                delete_folder(db_folder.case_id, db_folder.folder_path)
            except Exception as e:
                raise self._fail(
                    failed,
                    "physical_folder_error",
                    DomainException("Error deleting folder"),
                ) from e

        with transaction(self.db):
            for evidence in affected_evidence:
                provenance = self.db.get(models.CorrelationEvidence, evidence.id)
                if provenance is not None:
                    self.db.delete(provenance)
                self.db.delete(evidence)

        folder_logger.bind(
            case_id=db_folder.case_id,
            folder_title=db_folder.title,
            subfolder_count=len(affected_evidence),
            event_type="folder_deletion_success",
        ).info("Folder deleted successfully")

        return self._response(db_folder)

    async def create_folders_from_template(
        self,
        case_id: int,
        template_name: str,
        current_user: models.User,
    ) -> list[models.Evidence]:
        """Create folder structure from a template."""
        self.case_access.writable(current_user, case_id)
        template_logger = get_security_logger(
            user_id=current_user.id,
            case_id=case_id,
            action="apply_folder_template",
            template_name=template_name,
            event_type="folder_template_apply_attempt",
        )

        from app.services.system_config_service import SystemConfigService

        templates = await SystemConfigService(self.db).get_evidence_folder_templates()
        if template_name not in templates:
            raise self._fail(
                template_logger.bind(event_type="folder_template_apply_failed"),
                "template_not_found",
                ResourceNotFoundException(f"Template '{template_name}' not found"),
                available_templates=list(templates.keys()),
            )

        created_folders: list[models.Evidence] = []

        def create_folder_hierarchy(
            folders: list, parent_path: str = "", parent_id: int | None = None
        ):
            for folder_info in folders:
                folder_name = folder_info.get("name", "")
                if not folder_name:
                    continue

                folder_path = normalize_folder_path(
                    f"{parent_path}/{folder_name}" if parent_path else folder_name
                )
                new_folder = self._folder(
                    case_id,
                    folder_name,
                    folder_info.get("description", ""),
                    folder_path,
                    parent_id,
                    current_user,
                )
                self.db.add(new_folder)
                self.db.flush()

                create_folder(case_id, folder_path)

                created_folders.append(new_folder)

                subfolders = folder_info.get("subfolders", [])
                if subfolders:
                    create_folder_hierarchy(
                        subfolders, folder_path, cast(int, new_folder.id)
                    )

        with transaction(self.db):
            create_folder_hierarchy(templates[template_name].get("folders", []))

        for folder in created_folders:
            self.db.refresh(folder)

        template_logger.bind(
            folders_created=len(created_folders),
            template_used=template_name,
            event_type="folder_template_apply_success",
        ).info(f"Folder template '{template_name}' applied successfully")

        return created_folders
