"""
Evidence management API
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session
from typing import Optional

from app.database.connection import get_db
from app.database import models
from app.schemas import evidence_schema as schemas
from app.core.dependencies import get_current_active_user
from app.services.evidence_service import EvidenceService

router = APIRouter()


@router.post("/", response_model=list[schemas.Evidence])
async def create_evidence(
    title: str,
    case_id: int,
    category: str,
    description: Optional[str] = Form(None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one file must be provided")

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
        raise HTTPException(
            status_code=500, detail="Failed to upload any files"
        )

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
    return evidence_service.update_evidence(
        evidence_id=evidence_id,
        evidence_update=evidence,
        current_user=current_user,
    )


@router.delete("/{evidence_id}", response_model=schemas.Evidence)
async def delete_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    evidence_service = EvidenceService(db)
    return await evidence_service.delete_evidence(
        evidence_id=evidence_id, current_user=current_user
    )
