"""
Evidence management API
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlmodel import Session
from typing import Optional

from app.database.connection import get_db
from app.database import models
from app.schemas import evidence_schema as schemas
from app.core.dependencies import get_current_active_user
from app.services.evidence_service import EvidenceService
from app.services.exiftool_service import ExifToolService

router = APIRouter()


@router.post(
    "/", response_model=list[schemas.Evidence], status_code=status.HTTP_201_CREATED
)
async def create_evidence(
    title: str,
    case_id: int,
    category: str,
    description: Optional[str] = Form(None),
    folder_path: Optional[str] = Form(None),
    parent_folder_id: Optional[int] = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    if not files:
        raise HTTPException(
            status_code=400, detail="At least one file must be provided"
        )

    evidence_service = EvidenceService(db)
    results = []

    for file in files:
        evidence_data = schemas.EvidenceCreate(
            title=file.filename,
            description=description,
            category=category,
            case_id=case_id,
            evidence_type="file",
            content="",
            folder_path=folder_path,
            parent_folder_id=parent_folder_id,
        )

        try:
            evidence = await evidence_service.create_evidence(
                evidence=evidence_data, current_user=current_user, file=file
            )
            results.append(evidence)
        except Exception as e:
            # If one file fails, continue with the rest
            continue

    if not results:
        raise HTTPException(status_code=500, detail="Failed to upload any files")

    return results


@router.get("/case/{case_id}", response_model=list[schemas.Evidence])
async def read_case_evidence(
    case_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    evidence_service = EvidenceService(db)
    return await evidence_service.get_case_evidence(
        case_id=case_id, current_user=current_user, skip=skip, limit=limit
    )


@router.get("/{evidence_id}", response_model=schemas.Evidence)
async def read_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    evidence_service = EvidenceService(db)
    return await evidence_service.get_evidence(
        evidence_id=evidence_id, current_user=current_user
    )


@router.get("/{evidence_id}/download")
async def download_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    evidence_service = EvidenceService(db)
    return await evidence_service.download_evidence(
        evidence_id=evidence_id,
        current_user=current_user,
    )


@router.put("/{evidence_id}", response_model=schemas.Evidence)
async def update_evidence(
    evidence_id: int,
    evidence: schemas.EvidenceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    evidence_service = EvidenceService(db)
    return await evidence_service.update_evidence(
        evidence_id=evidence_id,
        evidence_update=evidence,
        current_user=current_user,
    )


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    evidence_service = EvidenceService(db)
    await evidence_service.delete_evidence(
        evidence_id=evidence_id, current_user=current_user
    )
    return {"message": "Evidence deleted successfully"}


@router.post(
    "/folders", response_model=schemas.Evidence, status_code=status.HTTP_201_CREATED
)
async def create_folder(
    folder_data: schemas.FolderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    evidence_service = EvidenceService(db)
    return await evidence_service.create_folder(
        folder_data=folder_data, current_user=current_user
    )


@router.get("/case/{case_id}/folder-tree", response_model=list[schemas.Evidence])
async def get_folder_tree(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    evidence_service = EvidenceService(db)
    return await evidence_service.get_folder_tree(
        case_id=case_id, current_user=current_user
    )


@router.put("/folders/{folder_id}", response_model=schemas.Evidence)
async def update_folder(
    folder_id: int,
    folder_update: schemas.FolderUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    evidence_service = EvidenceService(db)
    return await evidence_service.update_folder(
        folder_id=folder_id,
        folder_update=folder_update,
        current_user=current_user,
    )


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    evidence_service = EvidenceService(db)
    await evidence_service.delete_folder(folder_id=folder_id, current_user=current_user)
    return {"message": "Folder deleted successfully"}


@router.get("/{evidence_id}/metadata")
async def extract_evidence_metadata(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Extract metadata from evidence file using ExifTool"""
    evidence_service = EvidenceService(db)
    exiftool_service = ExifToolService()

    # Get the evidence record
    evidence = await evidence_service.get_evidence(
        evidence_id=evidence_id, current_user=current_user
    )

    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")

    if not evidence.content or evidence.is_folder:
        raise HTTPException(
            status_code=400,
            detail="Cannot extract metadata from folders or evidence without files",
        )

    # Check if file type is supported
    if not exiftool_service.is_supported_file(evidence.content):
        return {
            "success": False,
            "error": f"Unsupported file type for metadata extraction",
            "supported_file": False,
            "file_extension": (
                evidence.content.split(".")[-1]
                if "." in evidence.content
                else "unknown"
            ),
        }

    # Construct full file path
    from pathlib import Path
    from app.core.file_storage import UPLOAD_DIR

    full_file_path = UPLOAD_DIR / evidence.content

    # Extract metadata
    metadata_result = await exiftool_service.extract_metadata(str(full_file_path))

    if "error" in metadata_result:
        return {
            "success": False,
            "error": metadata_result["error"],
            "supported_file": True,
        }

    return metadata_result


@router.post(
    "/case/{case_id}/apply-template",
    response_model=list[schemas.Evidence],
    status_code=status.HTTP_201_CREATED,
)
async def apply_folder_template(
    case_id: int,
    template_name: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    """Apply a folder template to create folder structure for a case."""
    evidence_service = EvidenceService(db)
    return await evidence_service.create_folders_from_template(
        case_id=case_id,
        template_name=template_name,
        current_user=current_user,
    )
