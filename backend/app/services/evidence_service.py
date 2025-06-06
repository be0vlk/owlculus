"""
Evidence service for handling evidence-related operations.
"""

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select
from typing import List, Optional

from app.database import models
from app.schemas import evidence_schema as schemas
from app.core.utils import get_utc_now
from app.core.file_storage import save_upload_file, delete_file, create_folder, delete_folder, normalize_folder_path, UPLOAD_DIR
from app.core.dependencies import no_analyst


class EvidenceService:
    def __init__(self, db: Session):
        self.db = db

    async def create_evidence(
        self,
        evidence: schemas.EvidenceCreate,
        current_user: models.User,
        file: Optional[UploadFile] = None,
    ) -> models.Evidence:

        # Check if case exists
        case = self.db.exec(
            select(models.Case).where(models.Case.id == evidence.case_id)
        ).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Check if folders exist before allowing file uploads (excluding folder creation itself)
        if evidence.evidence_type == "file" and not evidence.is_folder:
            existing_folders = self.db.exec(
                select(models.Evidence).where(
                    models.Evidence.case_id == evidence.case_id,
                    models.Evidence.is_folder == True
                )
            ).first()
            if not existing_folders:
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot upload files without any folders. Create a folder first to organize evidence."
                )

        # For file uploads, save the file and get the path
        if evidence.evidence_type == "file" and not evidence.is_folder:
            if not file:
                raise HTTPException(
                    status_code=400, detail="File is required for file-type evidence"
                )
            try:
                # Save the file and get its path and hash
                relative_path, file_hash = await save_upload_file(
                    upload_file=file, case_id=evidence.case_id, folder_path=evidence.folder_path
                )
                evidence.content = relative_path
                evidence.file_hash = file_hash
            except HTTPException as e:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Error saving file: {str(e)}"
                )

        # Create the evidence record
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
            self.db.add(db_evidence)
            self.db.commit()
            self.db.refresh(db_evidence)
            return db_evidence
        except Exception as e:
            # If there was an error, try to delete the uploaded file
            if evidence.evidence_type == "file" and evidence.content:
                try:
                    await delete_file(evidence.content)
                except:
                    pass
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
        # Check if case exists
        case = self.db.exec(
            select(models.Case).where(models.Case.id == case_id)
        ).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Get evidence for the case
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
        return evidence

    def update_evidence(
        self,
        evidence_id: int,
        evidence_update: schemas.EvidenceUpdate,
        current_user: models.User,
    ) -> models.Evidence:
        # Get existing evidence
        db_evidence = self.db.get(models.Evidence, evidence_id)
        if not db_evidence:
            raise HTTPException(status_code=404, detail="Evidence not found")

        # Update fields if provided
        if evidence_update.title is not None:
            db_evidence.title = evidence_update.title
        if evidence_update.description is not None:
            db_evidence.description = evidence_update.description
        if evidence_update.content is not None:
            if db_evidence.evidence_type == "file":
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

        try:
            self.db.add(db_evidence)
            self.db.commit()
            self.db.refresh(db_evidence)
            return db_evidence
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Error updating evidence: {str(e)}"
            )

    @no_analyst()
    async def delete_evidence(
        self, evidence_id: int, current_user: models.User
    ) -> models.Evidence:
        evidence = await self.get_evidence(evidence_id, current_user)

        # Delete the file if it's a file-type evidence and has content
        if evidence.evidence_type == "file" and evidence.content:
            try:
                await delete_file(evidence.content)
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Error deleting file: {str(e)}"
                )

        # Delete the database record
        try:
            self.db.delete(evidence)
            self.db.commit()
            return evidence
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Error deleting evidence: {str(e)}"
            )

    async def download_evidence(
        self,
        evidence_id: int,
        current_user: models.User,
    ) -> models.Evidence:
        # Get evidence
        evidence = self.db.exec(
            select(models.Evidence).where(models.Evidence.id == evidence_id)
        ).first()
        if not evidence:
            raise HTTPException(status_code=404, detail="Evidence not found")

        # Check if user has access to the case
        case = self.db.exec(
            select(models.Case).where(models.Case.id == evidence.case_id)
        ).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # For file evidence, return a FileResponse
        if evidence.evidence_type == "file":
            from fastapi.responses import FileResponse
            from pathlib import Path
            from app.core.file_storage import UPLOAD_DIR

            file_path = UPLOAD_DIR / evidence.content
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="File not found")

            return FileResponse(
                path=str(file_path),
                filename=file_path.name,
                media_type="application/octet-stream",
            )

        raise HTTPException(
            status_code=400, detail="Evidence type does not support downloading"
        )

    async def create_folder(
        self,
        folder_data: schemas.FolderCreate,
        current_user: models.User,
    ) -> models.Evidence:
        """Create a new folder in the case directory."""
        # Check if case exists
        case = self.db.exec(
            select(models.Case).where(models.Case.id == folder_data.case_id)
        ).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Build folder path
        folder_path = folder_data.folder_path or ""
        if folder_data.parent_folder_id:
            parent_folder = self.db.get(models.Evidence, folder_data.parent_folder_id)
            if not parent_folder or not parent_folder.is_folder:
                raise HTTPException(status_code=404, detail="Parent folder not found")
            if parent_folder.folder_path:
                folder_path = f"{parent_folder.folder_path}/{folder_data.title}"
            else:
                folder_path = folder_data.title
        else:
            folder_path = folder_data.title

        # Create physical folder
        try:
            create_folder(folder_data.case_id, folder_path)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error creating folder: {str(e)}"
            )

        # Create folder record
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

        try:
            self.db.add(db_folder)
            self.db.commit()
            self.db.refresh(db_folder)
            return db_folder
        except Exception as e:
            # Clean up physical folder if database operation fails
            try:
                delete_folder(folder_data.case_id, folder_path)
            except:
                pass
            raise HTTPException(
                status_code=500, detail=f"Error creating folder record: {str(e)}"
            )

    async def get_folder_tree(
        self, case_id: int, current_user: models.User
    ) -> List[models.Evidence]:
        """Get the folder tree structure for a case."""
        # Check if case exists
        case = self.db.exec(
            select(models.Case).where(models.Case.id == case_id)
        ).first()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        # Get all evidence including folders for the case
        query = select(models.Evidence).where(models.Evidence.case_id == case_id)
        return list(self.db.exec(query))

    async def update_folder(
        self,
        folder_id: int,
        folder_update: schemas.FolderUpdate,
        current_user: models.User,
    ) -> models.Evidence:
        """Update a folder."""
        db_folder = self.db.get(models.Evidence, folder_id)
        if not db_folder or not db_folder.is_folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        # Update fields if provided
        if folder_update.title is not None:
            db_folder.title = folder_update.title
        if folder_update.description is not None:
            db_folder.description = folder_update.description
        if folder_update.parent_folder_id is not None:
            db_folder.parent_folder_id = folder_update.parent_folder_id

        db_folder.updated_at = get_utc_now()

        try:
            self.db.add(db_folder)
            self.db.commit()
            self.db.refresh(db_folder)
            return db_folder
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Error updating folder: {str(e)}"
            )

    @no_analyst()
    async def delete_folder(
        self, folder_id: int, current_user: models.User
    ) -> models.Evidence:
        """Delete a folder and all its contents."""
        db_folder = self.db.get(models.Evidence, folder_id)
        if not db_folder or not db_folder.is_folder:
            raise HTTPException(status_code=404, detail="Folder not found")

        # Delete physical folder and contents
        if db_folder.folder_path:
            try:
                delete_folder(db_folder.case_id, db_folder.folder_path)
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Error deleting folder: {str(e)}"
                )

        # Delete all evidence records in this folder and subfolders
        try:
            # Get all evidence in this folder path
            subfolder_evidence = self.db.exec(
                select(models.Evidence).where(
                    models.Evidence.case_id == db_folder.case_id,
                    models.Evidence.folder_path.like(f"{db_folder.folder_path}%")
                )
            ).all()

            # Delete all subfolder evidence
            for evidence in subfolder_evidence:
                self.db.delete(evidence)

            # Delete the folder record itself
            self.db.delete(db_folder)
            self.db.commit()
            return db_folder
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Error deleting folder record: {str(e)}"
            )
