"""Case, case membership and case entity routes."""

from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import FileResponse
from sqlmodel import Session
from starlette.background import BackgroundTask

from app import schemas
from app.core.database_boundary import DatabaseRoute
from app.core.dependencies import get_current_user
from app.database import models
from app.database.connection import get_db
from app.schemas.entity_schema import DuplicateAdvisory
from app.services.case_service import CaseService
from app.services.entity_service import EntityService
from app.services.export_service import EntityExportFormat, ExportService

router = APIRouter(route_class=DatabaseRoute)


@router.post("/", response_model=schemas.Case, status_code=status.HTTP_201_CREATED)
async def create_case(
    case: schemas.CaseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await CaseService(db).create_case(case=case, current_user=current_user)


@router.get("/", response_model=list[schemas.Case])
async def read_cases(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await CaseService(db).get_cases(
        current_user=current_user, skip=skip, limit=limit, status=status
    )


@router.get("/{case_id}", response_model=schemas.Case)
async def read_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await CaseService(db).get_case(case_id=case_id, current_user=current_user)


@router.put("/{case_id}", response_model=schemas.Case)
async def update_case(
    case_id: int,
    case: schemas.CaseUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await CaseService(db).update_case(
        case_id=case_id, case_update=case, current_user=current_user
    )


@router.post("/{case_id}/users/{user_id}", response_model=schemas.Case)
async def add_user_to_case(
    case_id: int,
    user_id: int,
    body: dict = {},
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    is_lead = body.get("is_lead", False) if body else False
    return await CaseService(db).add_user_to_case(
        case_id=case_id, user_id=user_id, current_user=current_user, is_lead=is_lead
    )


@router.patch("/{case_id}/users/{user_id}", response_model=schemas.Case)
async def update_case_user_lead_status(
    case_id: int,
    user_id: int,
    update_data: schemas.CaseUserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await CaseService(db).update_case_user_lead_status(
        case_id=case_id,
        user_id=user_id,
        is_lead=update_data.is_lead,
        current_user=current_user,
    )


@router.delete("/{case_id}/users/{user_id}", response_model=schemas.Case)
async def remove_user_from_case(
    case_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await CaseService(db).remove_user_from_case(
        case_id=case_id, user_id=user_id, current_user=current_user
    )


@router.get("/{case_id}/users", response_model=list[schemas.User])
async def get_case_users(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get all users assigned to a case"""
    case = await CaseService(db).get_case(case_id=case_id, current_user=current_user)
    return case.users


@router.get("/{case_id}/export")
async def export_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    artifact = ExportService(db).export_case_bundle(case_id, current_user)

    return FileResponse(
        path=artifact.path,
        media_type="application/zip",
        filename=artifact.filename,
        background=BackgroundTask(artifact.path.unlink, missing_ok=True),
    )


@router.get("/{case_id}/entities/export", tags=["entities"])
async def export_case_entities(
    case_id: int,
    format: EntityExportFormat = EntityExportFormat.CSV,
    entity_type: list[str] | None = Query(default=None),
    search: str | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    artifact = ExportService(db).export_entities(
        case_id=case_id,
        current_user=current_user,
        export_format=format,
        entity_types=entity_type,
        search=search,
    )

    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.filename}"'},
    )


@router.get(
    "/{case_id}/entities", response_model=List[schemas.Entity], tags=["entities"]
)
async def get_case_entities(
    case_id: int,
    entity_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await EntityService(db).get_case_entities(
        case_id=case_id,
        current_user=current_user,
        entity_type=entity_type,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/{case_id}/entities",
    response_model=schemas.Entity,
    tags=["entities"],
    status_code=status.HTTP_201_CREATED,
)
async def create_entity(
    case_id: int,
    entity: schemas.EntityCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await EntityService(db).create_entity(
        case_id=case_id, entity=entity, current_user=current_user
    )


@router.post(
    "/{case_id}/entities/duplicate-advisories",
    tags=["entities"],
    response_model=list[DuplicateAdvisory],
)
async def entity_duplicate_advisories(
    case_id: int,
    entity: schemas.EntityCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
    exclude_id: int | None = None,
):
    return await EntityService(db).duplicate_advisories(
        case_id, entity, current_user, exclude_id
    )


@router.put(
    "/{case_id}/entities/{entity_id}",
    response_model=schemas.Entity,
    tags=["entities"],
)
async def update_entity(
    case_id: int,
    entity_id: int,
    entity: schemas.EntityUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await EntityService(db).update_entity(
        case_id=case_id,
        entity_id=entity_id,
        entity_update=entity,
        current_user=current_user,
    )


@router.get(
    "/{case_id}/entities/{entity_id}",
    response_model=schemas.Entity,
    tags=["entities"],
)
async def get_entity(
    case_id: int,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return await EntityService(db).get_entity(
        case_id=case_id, entity_id=entity_id, current_user=current_user
    )


@router.delete(
    "/{case_id}/entities/{entity_id}",
    tags=["entities"],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_entity(
    case_id: int,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    await EntityService(db).delete_entity(
        case_id=case_id, entity_id=entity_id, current_user=current_user
    )
