"""
Evidence service for handling evidence-related operations.
"""

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select
from typing import List, Optional

from app.database import models
from app.schemas import evidence_schema as schemas
from app.core.utils import get_utc_now
from app.core.file_storage import save_upload_file, delete_file, UPLOAD_DIR
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

        # For file uploads, save the file and get the path
        if evidence.evidence_type == "file":
            if not file:
                raise HTTPException(
                    status_code=400, detail="File is required for file-type evidence"
                )
            try:
                # Save the file and get its path
                relative_path = await save_upload_file(
                    upload_file=file, case_id=evidence.case_id
                )
                evidence.content = relative_path
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
