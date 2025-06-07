"""
Client service layer handling all client-related business logic
"""

from sqlmodel import Session
from fastapi import HTTPException

from app.database import models, crud
from app import schemas
from app.core.dependencies import admin_only, no_analyst


class ClientService:
    def __init__(self, db: Session):
        self.db = db

    @no_analyst()
    async def get_clients(
        self, skip: int = 0, limit: int = 100, *, current_user: models.User
    ) -> list[models.Client]:
        if skip < 0 or limit < 0:
            raise ValueError("Skip and limit must be non-negative")
        return await crud.get_clients(self.db, skip=skip, limit=limit)

    @admin_only()
    async def create_client(
        self, client: schemas.ClientCreate, *, current_user: models.User
    ) -> models.Client:
        # Check for duplicate email
        existing = await crud.get_client_by_email(self.db, email=client.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        return await crud.create_client(self.db, client=client)

    @no_analyst()
    async def get_client(
        self, client_id: int, *, current_user: models.User
    ) -> models.Client:
        db_client = await crud.get_client(self.db, client_id=client_id)
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")
        return db_client

    @admin_only()
    async def update_client(
        self,
        client_id: int,
        client_update: schemas.ClientUpdate,
        *,
        current_user: models.User
    ) -> models.Client:
        db_client = await crud.get_client(self.db, client_id=client_id)
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Check email uniqueness if being updated
        if client_update.email and client_update.email != db_client.email:
            existing = await crud.get_client_by_email(
                self.db, email=client_update.email
            )
            if existing:
                raise HTTPException(status_code=400, detail="Email already registered")

        return await crud.update_client(
            self.db, client_id=client_id, client=client_update
        )

    @admin_only()
    async def delete_client(self, client_id: int, *, current_user: models.User) -> None:
        db_client = await crud.get_client(self.db, client_id=client_id)
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Check if client has any associated cases
        client_cases = await crud.get_cases(self.db)
        cases_for_client = [
            case for case in client_cases if case.client_id == client_id
        ]

        if cases_for_client:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete client with associated cases. Please remove or reassign all cases first.",
            )

        await crud.delete_client(self.db, client_id=client_id)
