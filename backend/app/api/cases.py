"""
Case management API
"""

from fastapi import APIRouter, Depends, status
from sqlmodel import Session
from typing import List
from typing import Optional

from app.database.connection import get_db
from app.database import models
from app import schemas
from app.core.dependencies import get_current_active_user
from app.services.case_service import CaseService
from app.services.entity_service import EntityService

router = APIRouter()


@router.post("/", response_model=schemas.Case, status_code=status.HTTP_201_CREATED)
async def create_case(
    case: schemas.CaseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    case_service = CaseService(db)
    return await case_service.create_case(case=case, current_user=current_user)


@router.get("/", response_model=list[schemas.Case])
async def read_cases(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    case_service = CaseService(db)
    return await case_service.get_cases(
        current_user=current_user, skip=skip, limit=limit, status=status
    )


@router.get("/{case_id}", response_model=schemas.Case)
async def read_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    case_service = CaseService(db)
    return await case_service.get_case(case_id=case_id, current_user=current_user)


@router.put("/{case_id}", response_model=schemas.Case)
async def update_case(
    case_id: int,
    case: schemas.CaseUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    case_service = CaseService(db)
    return await case_service.update_case(
        case_id=case_id, case_update=case, current_user=current_user
    )


@router.post("/{case_id}/users/{user_id}", response_model=schemas.Case)
async def add_user_to_case(
    case_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    case_service = CaseService(db)
    return await case_service.add_user_to_case(
        case_id=case_id, user_id=user_id, current_user=current_user
    )


@router.delete("/{case_id}/users/{user_id}", response_model=schemas.Case)
async def remove_user_from_case(
    case_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    case_service = CaseService(db)
    return await case_service.remove_user_from_case(
        case_id=case_id, user_id=user_id, current_user=current_user
    )


# Entity endpoints
@router.get(
    "/{case_id}/entities", response_model=List[schemas.Entity], tags=["entities"]
)
async def get_case_entities(
    case_id: int,
    entity_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    entity_service = EntityService(db)
    return await entity_service.get_case_entities(
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
    current_user: models.User = Depends(get_current_active_user),
):
    entity_service = EntityService(db)
    return await entity_service.create_entity(
        case_id=case_id, entity=entity, current_user=current_user
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
    current_user: models.User = Depends(get_current_active_user),
):
    entity_service = EntityService(db)
    return await entity_service.update_entity(
        entity_id=entity_id, entity_update=entity, current_user=current_user
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
    current_user: models.User = Depends(get_current_active_user),
):
    entity_service = EntityService(db)
    await entity_service.delete_entity(entity_id=entity_id, current_user=current_user)
    return {"message": "Entity deleted successfully"}
