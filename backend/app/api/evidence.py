"""Evidence and evidence folder routes."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.core import file_storage
from app.core.database_boundary import DatabaseRoute
from app.core.dependencies import get_current_user
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    DuplicateResourceException,
    PayloadTooLargeException,
    RelatedResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.database import models
from app.database.connection import get_db
from app.schemas import evidence_schema as schemas
from app.services.evidence_metadata import extract_metadata
from app.services.evidence_service import EvidenceService

router = APIRouter(route_class=DatabaseRoute)


@router.post(
    "/",
    response_model=schemas.EvidenceUploadResponse,
    status_code=status.HTTP_201_CREATED,
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
    current_user: models.User = Depends(get_current_user),
):
    if not files:
        raise ValidationException("At least one file must be provided")

    if len(files) > 10:
        raise PayloadTooLargeException(
            "Upload at most 10 files per request. No Evidence was saved."
        )

    evidence_service = EvidenceService(db)
    created: list[models.Evidence] = []
    failed: list[schemas.EvidenceUploadFailure] = []

    for file in files:
        evidence_data = schemas.EvidenceCreate(
            title=file.filename or "unknown",
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
            created.append(evidence)
        except (
            AuthenticationException,
            AuthorizationException,
            ResourceNotFoundException,
        ):
            raise
        except (
            DuplicateResourceException,
            RelatedResourceException,
            ValidationException,
        ) as error:
            failed.append(
                schemas.EvidenceUploadFailure(
                    filename=file.filename or "unknown", error=str(error)
                )
            )
        except Exception:  # noqa: BLE001 - each upload needs an explicit outcome
            failed.append(
                schemas.EvidenceUploadFailure(
                    filename=file.filename or "unknown",
                    error="Internal server error",
                )
            )

    created_responses = [
        schemas.Evidence.model_validate(evidence) for evidence in created
    ]
    return schemas.EvidenceUploadResponse(created=created_responses, failed=failed)


@router.get("/case/{case_id}", response_model=list[schemas.Evidence])
async def read_case_evidence(
    case_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await EvidenceService(db).get_case_evidence(
        case_id=case_id, current_user=current_user, skip=skip, limit=limit
    )


@router.get("/{evidence_id}", response_model=schemas.Evidence)
async def read_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await EvidenceService(db).get_evidence(
        evidence_id=evidence_id, current_user=current_user
    )


@router.get("/{evidence_id}/download")
async def download_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    file_path = await EvidenceService(db).download_evidence(
        evidence_id=evidence_id,
        current_user=current_user,
    )
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/octet-stream",
    )


@router.get("/{evidence_id}/content")
async def get_evidence_content(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await EvidenceService(db).get_evidence_content(
        evidence_id=evidence_id,
        current_user=current_user,
    )


@router.put("/{evidence_id}", response_model=schemas.Evidence)
async def update_evidence(
    evidence_id: int,
    evidence: schemas.EvidenceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return EvidenceService(db).update_evidence(
        evidence_id=evidence_id,
        evidence_update=evidence,
        current_user=current_user,
    )


@router.delete("/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    await EvidenceService(db).delete_evidence(
        evidence_id=evidence_id, current_user=current_user
    )


@router.post(
    "/folders", response_model=schemas.Evidence, status_code=status.HTTP_201_CREATED
)
async def create_folder(
    folder_data: schemas.FolderCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await EvidenceService(db).create_folder(
        folder_data=folder_data, current_user=current_user
    )


@router.get("/case/{case_id}/folder-tree", response_model=list[schemas.Evidence])
async def get_folder_tree(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await EvidenceService(db).get_case_evidence(
        case_id=case_id, current_user=current_user, limit=None
    )


@router.put("/folders/{folder_id}", response_model=schemas.Evidence)
async def update_folder(
    folder_id: int,
    folder_update: schemas.FolderUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await EvidenceService(db).update_folder(
        folder_id=folder_id,
        folder_update=folder_update,
        current_user=current_user,
    )


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    await EvidenceService(db).delete_folder(
        folder_id=folder_id, current_user=current_user
    )


@router.get("/{evidence_id}/metadata")
async def extract_evidence_metadata(
    evidence_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    evidence = await EvidenceService(db).get_evidence(
        evidence_id=evidence_id, current_user=current_user
    )
    if not evidence.content or evidence.is_folder:
        raise ValidationException(
            "Cannot extract metadata from folders or evidence without files"
        )
    try:
        path = file_storage.evidence_file_path(evidence.case_id, evidence.content)
    except ValueError as error:
        raise ValidationException(str(error)) from error
    return extract_metadata(path)


@router.post(
    "/case/{case_id}/apply-template",
    response_model=list[schemas.Evidence],
    status_code=status.HTTP_201_CREATED,
)
async def apply_folder_template(
    case_id: int,
    template_name: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await EvidenceService(db).create_folders_from_template(
        case_id=case_id,
        template_name=template_name,
        current_user=current_user,
    )
