"""
Case management API
"""

from typing import List, Optional

from app import schemas
from app.core.dependencies import admin_only, get_current_user, no_analyst
from app.core.exceptions import (
    AuthorizationException,
    BaseException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.database import models
from app.database.connection import get_db
from app.services.case_service import CaseService
from app.services.entity_service import EntityService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

router = APIRouter()


@router.post("/", response_model=schemas.Case, status_code=status.HTTP_201_CREATED)
@admin_only()
async def create_case(
    case: schemas.CaseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case_service = CaseService(db)
    try:
        return await case_service.create_case(case=case, current_user=current_user)
    except AuthorizationException:
        raise HTTPException(status_code=403, detail="Not authorized")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except BaseException:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/", response_model=list[schemas.Case])
async def read_cases(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case_service = CaseService(db)
    return await case_service.get_cases(
        current_user=current_user, skip=skip, limit=limit, status=status
    )


@router.get("/{case_id}", response_model=schemas.Case)
async def read_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case_service = CaseService(db)
    try:
        return await case_service.get_case(case_id=case_id, current_user=current_user)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.put("/{case_id}", response_model=schemas.Case)
@no_analyst()
async def update_case(
    case_id: int,
    case: schemas.CaseUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case_service = CaseService(db)
    try:
        return await case_service.update_case(
            case_id=case_id, case_update=case, current_user=current_user
        )
    except AuthorizationException:
        raise HTTPException(status_code=403, detail="Not authorized")
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except BaseException:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{case_id}/users/{user_id}", response_model=schemas.Case)
@admin_only()
async def add_user_to_case(
    case_id: int,
    user_id: int,
    body: dict = {},
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case_service = CaseService(db)
    try:
        # Get is_lead from body, default to False
        is_lead = body.get("is_lead", False) if body else False
        
        return await case_service.add_user_to_case(
            case_id=case_id, 
            user_id=user_id, 
            current_user=current_user,
            is_lead=is_lead
        )
    except AuthorizationException:
        raise HTTPException(status_code=403, detail="Not authorized")
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DuplicateResourceException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except BaseException:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.patch("/{case_id}/users/{user_id}", response_model=schemas.Case)
@admin_only()
async def update_case_user_lead_status(
    case_id: int,
    user_id: int,
    update_data: schemas.CaseUserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case_service = CaseService(db)
    try:
        return await case_service.update_case_user_lead_status(
            case_id=case_id,
            user_id=user_id,
            is_lead=update_data.is_lead,
            current_user=current_user
        )
    except AuthorizationException:
        raise HTTPException(status_code=403, detail="Not authorized")
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except BaseException:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/{case_id}/users/{user_id}", response_model=schemas.Case)
@admin_only()
async def remove_user_from_case(
    case_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case_service = CaseService(db)
    try:
        return await case_service.remove_user_from_case(
            case_id=case_id, user_id=user_id, current_user=current_user
        )
    except AuthorizationException:
        raise HTTPException(status_code=403, detail="Not authorized")
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BaseException:
        raise HTTPException(status_code=500, detail="Internal server error")


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
    current_user: models.User = Depends(get_current_user),
):
    entity_service = EntityService(db)
    try:
        return await entity_service.get_case_entities(
            case_id=case_id,
            current_user=current_user,
            entity_type=entity_type,
            skip=skip,
            limit=limit,
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post(
    "/{case_id}/entities",
    response_model=schemas.Entity,
    tags=["entities"],
    status_code=status.HTTP_201_CREATED,
)
@no_analyst()
async def create_entity(
    case_id: int,
    entity: schemas.EntityCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    entity_service = EntityService(db)
    try:
        return await entity_service.create_entity(
            case_id=case_id, entity=entity, current_user=current_user
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except BaseException:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.put(
    "/{case_id}/entities/{entity_id}",
    response_model=schemas.Entity,
    tags=["entities"],
)
@no_analyst()
async def update_entity(
    case_id: int,
    entity_id: int,
    entity: schemas.EntityUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    entity_service = EntityService(db)
    try:
        return await entity_service.update_entity(
            entity_id=entity_id, entity_update=entity, current_user=current_user
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except BaseException:
        raise HTTPException(status_code=500, detail="Internal server error")


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
    entity_service = EntityService(db)
    try:
        return await entity_service.get_entity(
            entity_id=entity_id, current_user=current_user
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.delete(
    "/{case_id}/entities/{entity_id}",
    tags=["entities"],
    status_code=status.HTTP_204_NO_CONTENT,
)
@no_analyst()
async def delete_entity(
    case_id: int,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    entity_service = EntityService(db)
    try:
        await entity_service.delete_entity(
            entity_id=entity_id, current_user=current_user
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=403, detail=str(e))
    except BaseException:
        raise HTTPException(status_code=500, detail="Internal server error")
