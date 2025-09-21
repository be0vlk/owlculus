"""
Evidence management service for Owlculus OSINT case file handling and storage.

This module handles all evidence-related operations including file uploads,
folder management, evidence validation, and secure file access. Provides
comprehensive evidence lifecycle management with file hashing, content viewing,
template-based folder structures, and role-based access control for OSINT investigations.
"""

from typing import List, Optional

from app.core.dependencies import check_case_access, no_analyst
from app.core.file_storage import (
	create_folder,
	delete_file,
	delete_folder,
	normalize_folder_path,
	save_upload_file,
)
from app.core.logging import get_security_logger
from app.core.utils import get_utc_now
from app.database import models
from app.schemas import evidence_schema as schemas
from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select


class EvidenceService:
    def __init__(self, db: Session):
        self.db = db

    @no_analyst()
    async def create_evidence(
        self,
        evidence: schemas.EvidenceCreate,
        current_user: models.User,
        file: Optional[UploadFile] = None,
    ) -> models.Evidence:
        evidence_logger = get_security_logger(
            user_id=current_user.id,
            case_id=evidence.case_id,
            action="create_evidence",
            evidence_type=evidence.evidence_type,
            event_type="evidence_creation_attempt",
        )

        try:
            try:
                case = check_case_access(self.db, evidence.case_id, current_user)
            except HTTPException as e:
                if e.status_code == 404:
                    evidence_logger.bind(
                        event_type="evidence_creation_failed",
                        failure_reason="case_not_found",
                    ).warning("Evidence creation failed: case not found")
                else:
                    evidence_logger.bind(
                        event_type="evidence_creation_failed",
                        failure_reason="not_authorized",
                    ).warning("Evidence creation failed: not authorized")
                raise

            # Prevent file uploads when no folder structure exists for organization
            if evidence.evidence_type == "file" and not evidence.is_folder:
                existing_folders = self.db.exec(
                    select(models.Evidence).where(
                        models.Evidence.case_id == evidence.case_id,
                        models.Evidence.is_folder == True,
                    )
                ).first()
                if not existing_folders:
                    evidence_logger.bind(
                        event_type="evidence_creation_failed",
                        failure_reason="no_folders_exist",
                    ).warning(
                        "Evidence creation failed: no folders exist for file upload"
                    )
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot upload files without any folders. Create a folder first to organize evidence.",
                    )

            if evidence.evidence_type == "file" and not evidence.is_folder:
                if not file:
                    evidence_logger.bind(
                        event_type="evidence_creation_failed",
                        failure_reason="file_required",
                    ).warning(
                        "Evidence creation failed: file required for file-type evidence"
                    )
                    raise HTTPException(
                        status_code=400,
                        detail="File is required for file-type evidence",
                    )
                try:
                    relative_path, file_hash = await save_upload_file(
                        upload_file=file,
                        case_id=evidence.case_id,
                        folder_path=evidence.folder_path,
                    )
                    evidence.content = relative_path
                    evidence.file_hash = file_hash
                    # Update title to reflect actual saved filename after duplicate handling
                    evidence.title = relative_path.split("/")[-1]
                except HTTPException:
                    raise
                except Exception as e:
                    evidence_logger.bind(
                        event_type="evidence_creation_failed",
                        failure_reason="file_save_error",
                    ).warning(f"Evidence creation failed: error saving file: {str(e)}")
                    raise HTTPException(
                        status_code=500, detail=f"Error saving file: {str(e)}"
                    )

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

            self.db.add(db_evidence)
            self.db.commit()
            self.db.refresh(db_evidence)

            evidence_logger.bind(
                evidence_id=db_evidence.id,
                evidence_title=db_evidence.title,
                evidence_category=db_evidence.category,
                event_type="evidence_creation_success",
            ).info("Evidence created successfully")

            return db_evidence

        except HTTPException:
            raise
        except Exception as e:
            # Clean up uploaded file on database operation failure
            if evidence.evidence_type == "file" and evidence.content:
                try:
                    await delete_file(evidence.content)
                except:
                    pass
            evidence_logger.bind(
                event_type="evidence_creation_error", error_type="system_error"
            ).error(f"Evidence creation error: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating evidence: {str(e)}"
            )

    async def get_case_evidence(
        self,
        case_id: int,
        current_user: models.User,
        skip: int = 0,
        limit: int = 100,
    ) -> List[models.Evidence]:
        check_case_access(self.db, case_id, current_user)

        query = (
            select(models.Evidence)
            .where(models.Evidence.case_id == case_id)
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.exec(query))

    async def get_evidence(
        self, evidence_id: int, current_user: models.User
    ) -> models.Evidence:
        evidence = self.db.get(models.Evidence, evidence_id)
        if not evidence:
            raise HTTPException(status_code=404, detail="Evidence not found")

        check_case_access(self.db, evidence.case_id, current_user)

        return evidence

    @no_analyst()
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

        try:
            db_evidence = self.db.get(models.Evidence, evidence_id)
            if not db_evidence:
                evidence_logger.bind(
                    event_type="evidence_update_failed",
                    failure_reason="evidence_not_found",
                ).warning("Evidence update failed: evidence not found")
                raise HTTPException(status_code=404, detail="Evidence not found")

            try:
                check_case_access(self.db, db_evidence.case_id, current_user)
            except HTTPException as e:
                if e.status_code == 404:
                    evidence_logger.bind(
                        event_type="evidence_update_failed",
                        failure_reason="case_not_found",
                    ).warning("Evidence update failed: case not found")
                else:
                    evidence_logger.bind(
                        event_type="evidence_update_failed",
                        failure_reason="not_authorized",
                    ).warning("Evidence update failed: not authorized")
                raise

            if evidence_update.title is not None:
                db_evidence.title = evidence_update.title
            if evidence_update.description is not None:
                db_evidence.description = evidence_update.description
            if evidence_update.content is not None:
                if db_evidence.evidence_type == "file":
                    evidence_logger.bind(
                        event_type="evidence_update_failed",
                        failure_reason="file_content_not_updatable",
                    ).warning(
                        "Evidence update failed: cannot update content of file-type evidence"
                    )
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot update content of file-type evidence",
                    )
                db_evidence.content = evidence_update.content
            if evidence_update.folder_path is not None:
                db_evidence.folder_path = evidence_update.folder_path
            if evidence_update.parent_folder_id is not None:
                db_evidence.parent_folder_id = evidence_update.parent_folder_id

            db_evidence.updated_at = get_utc_now()

            self.db.add(db_evidence)
            self.db.commit()
            self.db.refresh(db_evidence)

            evidence_logger.bind(
                case_id=db_evidence.case_id,
                evidence_title=db_evidence.title,
                event_type="evidence_update_success",
            ).info("Evidence updated successfully")

            return db_evidence

        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            evidence_logger.bind(
                event_type="evidence_update_error", error_type="system_error"
            ).error(f"Evidence update error: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error updating evidence: {str(e)}"
            )

    @no_analyst()
    async def delete_evidence(
        self, evidence_id: int, current_user: models.User
    ) -> models.Evidence:
        evidence_logger = get_security_logger(
            user_id=current_user.id,
            evidence_id=evidence_id,
            action="delete_evidence",
            event_type="evidence_deletion_attempt",
        )

        try:
            evidence = self.db.get(models.Evidence, evidence_id)
            if not evidence:
                # Handle race condition where evidence may already be deleted in bulk operations
                evidence_logger.bind(
                    event_type="evidence_already_deleted",
                ).info("Evidence already deleted or not found")
                return None

            try:
                check_case_access(self.db, evidence.case_id, current_user)
            except HTTPException:
                evidence_logger.bind(
                    event_type="evidence_deletion_failed",
                    failure_reason="not_authorized",
                ).warning("Evidence deletion failed: not authorized")
                raise

            if evidence.evidence_type == "file" and evidence.content:
                try:
                    await delete_file(evidence.content)
                except Exception as e:
                    evidence_logger.bind(
                        event_type="evidence_deletion_failed",
                        failure_reason="file_deletion_error",
                    ).warning(
                        f"Evidence deletion failed: error deleting file: {str(e)}"
                    )
                    raise HTTPException(
                        status_code=500, detail=f"Error deleting file: {str(e)}"
                    )

            self.db.delete(evidence)
            self.db.commit()

            evidence_logger.bind(
                case_id=evidence.case_id,
                evidence_title=evidence.title,
                evidence_type=evidence.evidence_type,
                event_type="evidence_deletion_success",
            ).info("Evidence deleted successfully")

            return evidence

        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            evidence_logger.bind(
                event_type="evidence_deletion_error", error_type="system_error"
            ).error(f"Evidence deletion error: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error deleting evidence: {str(e)}"
            )

    async def download_evidence(
        self,
        evidence_id: int,
        current_user: models.User,
    ) -> models.Evidence:
        evidence_logger = get_security_logger(
            user_id=current_user.id,
            evidence_id=evidence_id,
            action="download_evidence",
            event_type="evidence_download_attempt",
        )

        try:
            evidence = self.db.exec(
                select(models.Evidence).where(models.Evidence.id == evidence_id)
            ).first()
            if not evidence:
                evidence_logger.bind(
                    event_type="evidence_download_failed",
                    failure_reason="evidence_not_found",
                ).warning("Evidence download failed: evidence not found")
                raise HTTPException(status_code=404, detail="Evidence not found")

            try:
                check_case_access(self.db, evidence.case_id, current_user)
            except HTTPException as e:
                if e.status_code == 404:
                    evidence_logger.bind(
                        event_type="evidence_download_failed",
                        failure_reason="case_not_found",
                    ).warning("Evidence download failed: case not found")
                else:
                    evidence_logger.bind(
                        event_type="evidence_download_failed",
                        failure_reason="not_authorized",
                    ).warning("Evidence download failed: not authorized")
                raise

            if evidence.evidence_type == "file":

                from app.core.file_storage import UPLOAD_DIR
                from fastapi.responses import FileResponse

                file_path = UPLOAD_DIR / evidence.content
                if not file_path.exists():
                    evidence_logger.bind(
                        event_type="evidence_download_failed",
                        failure_reason="file_not_found",
                        file_path=str(file_path),
                    ).warning("Evidence download failed: file not found on disk")
                    raise HTTPException(status_code=404, detail="File not found")

                evidence_logger.bind(
                    case_id=evidence.case_id,
                    evidence_title=evidence.title,
                    filename=file_path.name,
                    event_type="evidence_download_success",
                ).info("Evidence downloaded successfully")

                return FileResponse(
                    path=str(file_path),
                    filename=file_path.name,
                    media_type="application/octet-stream",
                )

            evidence_logger.bind(
                event_type="evidence_download_failed",
                failure_reason="unsupported_evidence_type",
                evidence_type=evidence.evidence_type,
            ).warning(
                "Evidence download failed: evidence type does not support downloading"
            )
            raise HTTPException(
                status_code=400, detail="Evidence type does not support downloading"
            )

        except HTTPException:
            raise
        except Exception as e:
            evidence_logger.bind(
                event_type="evidence_download_error", error_type="system_error"
            ).error(f"Evidence download error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

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

        try:
            evidence = await self.get_evidence(evidence_id, current_user)

            if evidence.is_folder:
                evidence_logger.bind(
                    event_type="evidence_content_view_failed",
                    failure_reason="is_folder",
                ).warning("Evidence content view failed: evidence is a folder")
                raise HTTPException(
                    status_code=400, detail="Cannot view content of folders"
                )

            if evidence.evidence_type != "file":
                evidence_logger.bind(
                    event_type="evidence_content_view_failed",
                    failure_reason="not_file_type",
                    evidence_type=evidence.evidence_type,
                ).warning("Evidence content view failed: evidence is not a file")
                raise HTTPException(
                    status_code=400,
                    detail="Evidence type does not support content viewing",
                )

            import chardet
            from app.core.file_storage import UPLOAD_DIR

            file_path = UPLOAD_DIR / evidence.content
            if not file_path.exists():
                evidence_logger.bind(
                    event_type="evidence_content_view_failed",
                    failure_reason="file_not_found",
                    file_path=str(file_path),
                ).warning("Evidence content view failed: file not found on disk")
                raise HTTPException(status_code=404, detail="File not found")

            # Limit file size to prevent memory issues with large files
            file_size = file_path.stat().st_size
            max_size = 1024 * 1024
            if file_size > max_size:
                evidence_logger.bind(
                    event_type="evidence_content_view_failed",
                    failure_reason="file_too_large",
                    file_size=file_size,
                    max_size=max_size,
                ).warning("Evidence content view failed: file too large")
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large for viewing. Maximum size: {max_size // 1024}KB",
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
                evidence_logger.bind(
                    event_type="evidence_content_view_failed",
                    failure_reason="unsupported_file_type",
                    file_extension=file_extension,
                ).warning("Evidence content view failed: unsupported file type")
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '{file_extension}' is not supported for text viewing",
                )

            try:
                with open(file_path, "rb") as f:
                    raw_content = f.read()

                encoding_result = chardet.detect(raw_content)
                encoding = encoding_result.get("encoding", "utf-8")
                confidence = encoding_result.get("confidence", 0)

                # Decode with detected encoding, fallback to utf-8 with error replacement
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

            except Exception as e:
                evidence_logger.bind(
                    event_type="evidence_content_view_failed",
                    failure_reason="file_read_error",
                ).warning(f"Evidence content view failed: error reading file: {str(e)}")
                raise HTTPException(
                    status_code=500, detail=f"Error reading file content: {str(e)}"
                )

        except HTTPException:
            raise
        except Exception as e:
            evidence_logger.bind(
                event_type="evidence_content_view_error", error_type="system_error"
            ).error(f"Evidence content view error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def get_evidence_image(
        self,
        evidence_id: int,
        current_user: models.User,
    ):
        """Get image file for viewing."""
        evidence_logger = get_security_logger(
            user_id=current_user.id,
            evidence_id=evidence_id,
            action="get_evidence_image",
            event_type="evidence_image_view_attempt",
        )

        try:
            evidence = await self.get_evidence(evidence_id, current_user)

            if evidence.is_folder:
                evidence_logger.bind(
                    event_type="evidence_image_view_failed",
                    failure_reason="is_folder",
                ).warning("Evidence image view failed: evidence is a folder")
                raise HTTPException(
                    status_code=400, detail="Cannot view images from folders"
                )

            if evidence.evidence_type != "file":
                evidence_logger.bind(
                    event_type="evidence_image_view_failed",
                    failure_reason="not_file_type",
                    evidence_type=evidence.evidence_type,
                ).warning("Evidence image view failed: evidence is not a file")
                raise HTTPException(
                    status_code=400,
                    detail="Evidence type does not support image viewing",
                )

            from app.core.file_storage import UPLOAD_DIR
            from fastapi.responses import FileResponse

            file_path = UPLOAD_DIR / evidence.content
            if not file_path.exists():
                evidence_logger.bind(
                    event_type="evidence_image_view_failed",
                    failure_reason="file_not_found",
                    file_path=str(file_path),
                ).warning("Evidence image view failed: file not found on disk")
                raise HTTPException(status_code=404, detail="File not found")

            viewable_extensions = {
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".bmp",
                ".webp",
                ".svg",
            }
            file_extension = file_path.suffix.lower()

            if file_extension not in viewable_extensions:
                evidence_logger.bind(
                    event_type="evidence_image_view_failed",
                    failure_reason="unsupported_file_type",
                    file_extension=file_extension,
                ).warning("Evidence image view failed: unsupported file type")
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '{file_extension}' is not supported for image viewing",
                )

            # Limit image size to prevent excessive memory usage
            file_size = file_path.stat().st_size
            max_size = 10 * 1024 * 1024
            if file_size > max_size:
                evidence_logger.bind(
                    event_type="evidence_image_view_failed",
                    failure_reason="file_too_large",
                    file_size=file_size,
                    max_size=max_size,
                ).warning("Evidence image view failed: file too large")
                raise HTTPException(
                    status_code=400,
                    detail=f"Image too large for viewing. Maximum size: {max_size // 1024 // 1024}MB",
                )

            media_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".bmp": "image/bmp",
                ".webp": "image/webp",
                ".svg": "image/svg+xml",
            }
            media_type = media_types.get(file_extension, "application/octet-stream")

            evidence_logger.bind(
                case_id=evidence.case_id,
                evidence_title=evidence.title,
                filename=file_path.name,
                event_type="evidence_image_view_success",
            ).info("Evidence image viewed successfully")

            return FileResponse(
                path=str(file_path),
                media_type=media_type,
                headers={
                    "Cache-Control": "max-age=3600",
                    "X-Content-Type-Options": "nosniff",
                },
            )

        except HTTPException:
            raise
        except Exception as e:
            evidence_logger.bind(
                event_type="evidence_image_view_error", error_type="system_error"
            ).error(f"Evidence image view error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @no_analyst()
    async def create_folder(
        self,
        folder_data: schemas.FolderCreate,
        current_user: models.User,
    ) -> models.Evidence:
        """Create a new folder in the case directory."""
        folder_logger = get_security_logger(
            user_id=current_user.id,
            case_id=folder_data.case_id,
            action="create_folder",
            folder_title=folder_data.title,
            event_type="folder_creation_attempt",
        )

        try:
            try:
                check_case_access(self.db, folder_data.case_id, current_user)
            except HTTPException as e:
                if e.status_code == 404:
                    folder_logger.bind(
                        event_type="folder_creation_failed",
                        failure_reason="case_not_found",
                    ).warning("Folder creation failed: case not found")
                else:
                    folder_logger.bind(
                        event_type="folder_creation_failed",
                        failure_reason="not_authorized",
                    ).warning("Folder creation failed: not authorized")
                raise

            folder_path = folder_data.folder_path or ""
            if folder_data.parent_folder_id:
                parent_folder = self.db.get(
                    models.Evidence, folder_data.parent_folder_id
                )
                if not parent_folder or not parent_folder.is_folder:
                    folder_logger.bind(
                        event_type="folder_creation_failed",
                        failure_reason="parent_folder_not_found",
                    ).warning("Folder creation failed: parent folder not found")
                    raise HTTPException(
                        status_code=404, detail="Parent folder not found"
                    )
                if parent_folder.folder_path:
                    folder_path = f"{parent_folder.folder_path}/{folder_data.title}"
                else:
                    folder_path = folder_data.title
            else:
                folder_path = folder_data.title

            try:
                create_folder(folder_data.case_id, folder_path)
            except HTTPException:
                raise
            except Exception as e:
                folder_logger.bind(
                    event_type="folder_creation_failed",
                    failure_reason="physical_folder_error",
                ).warning(
                    f"Folder creation failed: error creating physical folder: {str(e)}"
                )
                raise HTTPException(
                    status_code=500, detail=f"Error creating folder: {str(e)}"
                )

            db_folder = models.Evidence(
                case_id=folder_data.case_id,
                title=folder_data.title,
                description=folder_data.description,
                evidence_type="folder",
                category="Other",
                content="",
                folder_path=folder_path,
                is_folder=True,
                parent_folder_id=folder_data.parent_folder_id,
                created_by_id=current_user.id,
                created_at=get_utc_now(),
                updated_at=get_utc_now(),
            )

            self.db.add(db_folder)
            self.db.commit()
            self.db.refresh(db_folder)

            folder_logger.bind(
                folder_id=db_folder.id,
                folder_path=folder_path,
                event_type="folder_creation_success",
            ).info("Folder created successfully")

            return db_folder

        except HTTPException:
            raise
        except Exception as e:
            # Clean up physical folder on database failure
            try:
                delete_folder(folder_data.case_id, folder_path)
            except:
                pass
            folder_logger.bind(
                event_type="folder_creation_error", error_type="system_error"
            ).error(f"Folder creation error: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error creating folder record: {str(e)}"
            )

    async def get_folder_tree(
        self, case_id: int, current_user: models.User
    ) -> List[models.Evidence]:
        """Get the folder tree structure for a case."""
        check_case_access(self.db, case_id, current_user)

        query = select(models.Evidence).where(models.Evidence.case_id == case_id)
        return list(self.db.exec(query))

    @no_analyst()
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

        try:
            db_folder = self.db.get(models.Evidence, folder_id)
            if not db_folder or not db_folder.is_folder:
                folder_logger.bind(
                    event_type="folder_update_failed", failure_reason="folder_not_found"
                ).warning("Folder update failed: folder not found")
                raise HTTPException(status_code=404, detail="Folder not found")

            try:
                check_case_access(self.db, db_folder.case_id, current_user)
            except HTTPException as e:
                if e.status_code == 404:
                    folder_logger.bind(
                        event_type="folder_update_failed",
                        failure_reason="case_not_found",
                    ).warning("Folder update failed: case not found")
                else:
                    folder_logger.bind(
                        event_type="folder_update_failed",
                        failure_reason="not_authorized",
                    ).warning("Folder update failed: not authorized")
                raise

            if folder_update.title is not None:
                db_folder.title = folder_update.title
            if folder_update.description is not None:
                db_folder.description = folder_update.description
            if folder_update.parent_folder_id is not None:
                db_folder.parent_folder_id = folder_update.parent_folder_id

            db_folder.updated_at = get_utc_now()

            self.db.add(db_folder)
            self.db.commit()
            self.db.refresh(db_folder)

            folder_logger.bind(
                case_id=db_folder.case_id,
                folder_title=db_folder.title,
                event_type="folder_update_success",
            ).info("Folder updated successfully")

            return db_folder

        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            folder_logger.bind(
                event_type="folder_update_error", error_type="system_error"
            ).error(f"Folder update error: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error updating folder: {str(e)}"
            )

    @no_analyst()
    async def delete_folder(
        self, folder_id: int, current_user: models.User
    ) -> models.Evidence:
        """Delete a folder and all its contents."""
        folder_logger = get_security_logger(
            user_id=current_user.id,
            folder_id=folder_id,
            action="delete_folder",
            event_type="folder_deletion_attempt",
        )

        try:
            db_folder = self.db.get(models.Evidence, folder_id)
            if not db_folder:
                # Handle race condition in bulk delete operations
                folder_logger.bind(
                    event_type="folder_already_deleted",
                ).info("Folder already deleted or not found")
                return None

            if not db_folder.is_folder:
                folder_logger.bind(
                    event_type="folder_deletion_failed",
                    failure_reason="not_a_folder",
                ).warning("Folder deletion failed: not a folder")
                raise HTTPException(status_code=404, detail="Folder not found")

            try:
                check_case_access(self.db, db_folder.case_id, current_user)
            except HTTPException as e:
                if e.status_code == 404:
                    folder_logger.bind(
                        event_type="folder_deletion_failed",
                        failure_reason="case_not_found",
                    ).warning("Folder deletion failed: case not found")
                else:
                    folder_logger.bind(
                        event_type="folder_deletion_failed",
                        failure_reason="not_authorized",
                    ).warning("Folder deletion failed: not authorized")
                raise

            if db_folder.folder_path:
                try:
                    delete_folder(db_folder.case_id, db_folder.folder_path)
                except Exception as e:
                    folder_logger.bind(
                        event_type="folder_deletion_failed",
                        failure_reason="physical_folder_error",
                    ).warning(
                        f"Folder deletion failed: error deleting physical folder: {str(e)}"
                    )
                    raise HTTPException(
                        status_code=500, detail=f"Error deleting folder: {str(e)}"
                    )

            # Remove all evidence records within this folder hierarchy
            subfolder_evidence = self.db.exec(
                select(models.Evidence).where(
                    models.Evidence.case_id == db_folder.case_id,
                    models.Evidence.folder_path.like(f"{db_folder.folder_path}%"),
                )
            ).all()

            for evidence in subfolder_evidence:
                self.db.delete(evidence)

            self.db.delete(db_folder)
            self.db.commit()

            folder_logger.bind(
                case_id=db_folder.case_id,
                folder_title=db_folder.title,
                subfolder_count=len(subfolder_evidence),
                event_type="folder_deletion_success",
            ).info("Folder deleted successfully")

            return db_folder

        except HTTPException:
            raise
        except Exception as e:
            self.db.rollback()
            folder_logger.bind(
                event_type="folder_deletion_error", error_type="system_error"
            ).error(f"Folder deletion error: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error deleting folder record: {str(e)}"
            )

    async def create_folders_from_template(
        self,
        case_id: int,
        template_name: str,
        current_user: models.User,
    ) -> List[models.Evidence]:
        """Create folder structure from a template."""
        template_logger = get_security_logger(
            user_id=current_user.id,
            case_id=case_id,
            action="apply_folder_template",
            template_name=template_name,
            event_type="folder_template_apply_attempt",
        )

        try:
            try:
                check_case_access(self.db, case_id, current_user)
            except HTTPException as e:
                if e.status_code == 404:
                    template_logger.bind(
                        event_type="folder_template_apply_failed",
                        failure_reason="case_not_found",
                    ).warning("Folder template apply failed: case not found")
                else:
                    template_logger.bind(
                        event_type="folder_template_apply_failed",
                        failure_reason="not_authorized",
                    ).warning("Folder template apply failed: not authorized")
                raise

            from app.services.system_config_service import SystemConfigService

            config_service = SystemConfigService(self.db)
            templates = await config_service.get_evidence_folder_templates()

            if template_name not in templates:
                template_logger.bind(
                    event_type="folder_template_apply_failed",
                    failure_reason="template_not_found",
                    available_templates=list(templates.keys()),
                ).warning(
                    f"Folder template apply failed: template '{template_name}' not found"
                )
                raise HTTPException(
                    status_code=404, detail=f"Template '{template_name}' not found"
                )

            template = templates[template_name]
            created_folders = []

            def create_folder_hierarchy(
                folders: list, parent_path: str = "", parent_id: Optional[int] = None
            ):
                for folder_info in folders:
                    folder_name = folder_info.get("name", "")
                    if not folder_name:
                        continue

                    folder_path = (
                        f"{parent_path}/{folder_name}" if parent_path else folder_name
                    )

                    folder_data = schemas.FolderCreate(
                        title=folder_name,
                        description=folder_info.get("description", ""),
                        case_id=case_id,
                        folder_path=folder_path,
                        parent_folder_id=parent_id,
                    )

                    new_folder = models.Evidence(
                        case_id=folder_data.case_id,
                        title=folder_data.title,
                        description=folder_data.description,
                        evidence_type="folder",
                        category="Other",
                        content="",
                        is_folder=True,
                        folder_path=normalize_folder_path(folder_data.folder_path),
                        parent_folder_id=folder_data.parent_folder_id,
                        created_by_id=current_user.id,
                        created_at=get_utc_now(),
                        updated_at=get_utc_now(),
                    )
                    self.db.add(new_folder)
                    self.db.flush()

                    create_folder(case_id, new_folder.folder_path)

                    created_folders.append(new_folder)

                    subfolders = folder_info.get("subfolders", [])
                    if subfolders:
                        create_folder_hierarchy(
                            subfolders, new_folder.folder_path, new_folder.id
                        )

            template_folders = template.get("folders", [])
            create_folder_hierarchy(template_folders)

            self.db.commit()

            for folder in created_folders:
                self.db.refresh(folder)

            template_logger.bind(
                folders_created=len(created_folders),
                template_used=template_name,
                event_type="folder_template_apply_success",
            ).info(f"Folder template '{template_name}' applied successfully")

            return created_folders

        except HTTPException:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            template_logger.bind(
                event_type="folder_template_apply_error",
                error_type="system_error",
            ).error(f"Folder template apply error: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error applying folder template: {str(e)}"
            )
