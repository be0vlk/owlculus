"""
Client management service for Owlculus OSINT case management platform.

This module handles all client-related business logic including client registration,
profile management, and data validation. Provides secure client operations with
email uniqueness enforcement, comprehensive error handling, and audit logging
for OSINT investigation client management.
"""

from sqlmodel import Session, select

from app import schemas
from app.core.exceptions import (
    DomainException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.logging import audit_operation
from app.core.utils import get_utc_now
from app.database import models
from app.database.db_utils import transaction
from app.services.case_access import CaseAccess


class ClientService:
    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)

    def _with_readable_cases(
        self, clients: list[models.Client], user: models.User
    ) -> list[schemas.Client]:
        readable = set(self.case_access.readable_case_ids(user))
        views = [schemas.Client.model_validate(client) for client in clients]
        for view in views:
            view.cases = [case for case in view.cases if case.id in readable]
        return views

    async def get_clients(
        self, skip: int = 0, limit: int = 100, *, current_user: models.User
    ) -> list[schemas.Client]:
        self.case_access.require_non_analyst(current_user)
        if skip < 0 or limit < 0:
            raise ValidationException("Skip and limit must be non-negative")
        clients = self.db.exec(select(models.Client).offset(skip).limit(limit)).all()
        return self._with_readable_cases(list(clients), current_user)

    @audit_operation("client_creation")
    async def create_client(
        self, client: schemas.ClientCreate, *, current_user: models.User
    ) -> schemas.Client:
        self.case_access.require_admin(current_user)
        if (
            client.email
            and self.db.exec(
                select(models.Client).where(models.Client.email == client.email)
            ).first()
        ):
            raise DuplicateResourceException("Email already registered")

        new_client = models.Client(**client.model_dump())
        with transaction(self.db):
            self.db.add(new_client)
        self.db.refresh(new_client)
        return self._with_readable_cases([new_client], current_user)[0]

    def _get_client(self, client_id: int) -> models.Client:
        db_client = self.db.get(models.Client, client_id)
        if not db_client:
            raise ResourceNotFoundException(f"Client with id {client_id} not found")
        return db_client

    async def get_client(
        self, client_id: int, *, current_user: models.User
    ) -> schemas.Client:
        self.case_access.require_non_analyst(current_user)
        return self._with_readable_cases([self._get_client(client_id)], current_user)[0]

    @audit_operation("client_update")
    async def update_client(
        self,
        client_id: int,
        client_update: schemas.ClientUpdate,
        *,
        current_user: models.User,
    ) -> schemas.Client:
        self.case_access.require_admin(current_user)
        db_client = self._get_client(client_id)
        if client_update.email and client_update.email != db_client.email:
            existing = self.db.exec(
                select(models.Client).where(models.Client.email == client_update.email)
            ).first()
            if existing:
                raise DuplicateResourceException("Email already registered")

        with transaction(self.db):
            update_data = client_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_client, field, value)
            db_client.updated_at = get_utc_now()
            self.db.add(db_client)
        self.db.refresh(db_client)
        return self._with_readable_cases([db_client], current_user)[0]

    @audit_operation("client_deletion")
    async def delete_client(self, client_id: int, *, current_user: models.User) -> None:
        self.case_access.require_admin(current_user)
        db_client = self._get_client(client_id)
        if self.db.exec(
            select(models.Case).where(models.Case.client_id == client_id)
        ).first():
            raise DomainException(
                "Cannot delete client with associated cases. Please remove or reassign all cases first."
            )

        with transaction(self.db):
            self.db.delete(db_client)
