"""
Client management API
"""

from app import schemas
from app.core.dependencies import get_current_user, admin_only, no_analyst
from app.core.exceptions import (
    DuplicateResourceException,
    ResourceNotFoundException,
    BaseException,
)
from app.database import models
from app.database.connection import get_db
from app.services.client_service import ClientService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

router = APIRouter()


@router.get("/", response_model=list[schemas.Client])
@no_analyst()
async def read_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client_service = ClientService(db)
    return await client_service.get_clients(
        current_user=current_user, skip=skip, limit=limit
    )


@router.post("/", response_model=schemas.Client, status_code=status.HTTP_201_CREATED)
@admin_only()
async def create_client(
    client: schemas.ClientCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client_service = ClientService(db)
    try:
        return await client_service.create_client(
            client=client, current_user=current_user
        )
    except DuplicateResourceException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{client_id}", response_model=schemas.Client)
@no_analyst()
async def read_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client_service = ClientService(db)
    try:
        return await client_service.get_client(
            client_id=client_id, current_user=current_user
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{client_id}", response_model=schemas.Client)
@admin_only()
async def update_client(
    client_id: int,
    client: schemas.ClientUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client_service = ClientService(db)
    try:
        return await client_service.update_client(
            client_id=client_id, client_update=client, current_user=current_user
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DuplicateResourceException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
@admin_only()
async def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    client_service = ClientService(db)
    try:
        await client_service.delete_client(
            client_id=client_id, current_user=current_user
        )
        return {"message": "Client deleted successfully"}
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BaseException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
