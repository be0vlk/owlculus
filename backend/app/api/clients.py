"""
Client management API
"""

from fastapi import APIRouter, Depends, status
from sqlmodel import Session

from app.database.connection import get_db
from app.database import models
from app import schemas
from app.core.dependencies import get_current_active_user
from app.services.client_service import ClientService

router = APIRouter()


@router.get("/", response_model=list[schemas.Client])
async def read_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    client_service = ClientService(db)
    return await client_service.get_clients(
        current_user=current_user, skip=skip, limit=limit
    )


@router.post("/", response_model=schemas.Client, status_code=status.HTTP_201_CREATED)
async def create_client(
    client: schemas.ClientCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    client_service = ClientService(db)
    return await client_service.create_client(client=client, current_user=current_user)


@router.get("/{client_id}", response_model=schemas.Client)
async def read_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    client_service = ClientService(db)
    return await client_service.get_client(
        client_id=client_id, current_user=current_user
    )


@router.put("/{client_id}", response_model=schemas.Client)
async def update_client(
    client_id: int,
    client: schemas.ClientUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    client_service = ClientService(db)
    return await client_service.update_client(
        client_id=client_id, client_update=client, current_user=current_user
    )


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    client_service = ClientService(db)
    await client_service.delete_client(client_id=client_id, current_user=current_user)
    return {"message": "Client deleted successfully"}
