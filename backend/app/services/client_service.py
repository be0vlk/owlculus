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
    BaseException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.logging import get_security_logger
from app.core.utils import get_utc_now
from app.database import models
from app.database.db_utils import transaction
from app.services.case_access import CaseAccess


class ClientService:
    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)

    async def get_clients(
        self, skip: int = 0, limit: int = 100, *, current_user: models.User
    ) -> list[models.Client]:
        self.case_access.require_non_analyst(current_user)
        if skip < 0 or limit < 0:
            raise ValidationException("Skip and limit must be non-negative")
        return list(self.db.exec(select(models.Client).offset(skip).limit(limit)).all())

    async def create_client(
        self, client: schemas.ClientCreate, *, current_user: models.User
    ) -> models.Client:
        self.case_access.require_admin(current_user)
        client_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="create_client",
            client_name=client.name,
            event_type="client_creation_attempt",
        )

        try:
            existing = self.db.exec(
                select(models.Client).where(models.Client.email == client.email)
            ).first()
            if existing:
                client_logger.bind(
                    event_type="client_creation_failed", failure_reason="email_exists"
                ).warning("Client creation failed: email already registered")
                raise DuplicateResourceException("Email already registered")

            new_client = models.Client(**client.model_dump())
            with transaction(self.db):
                self.db.add(new_client)
            self.db.refresh(new_client)

            client_logger.bind(
                client_id=new_client.id,
                client_email=new_client.email,
                event_type="client_creation_success",
            ).info("Client created successfully")

            return new_client

        except DuplicateResourceException:
            raise
        except Exception as e:
            client_logger.bind(
                event_type="client_creation_error", error_type="system_error"
            ).error(f"Client creation error: {e!s}")
            raise BaseException(f"Client creation error: {e!s}")

    async def get_client(
        self, client_id: int, *, current_user: models.User
    ) -> models.Client:
        self.case_access.require_non_analyst(current_user)
        db_client = self.db.get(models.Client, client_id)
        if not db_client:
            raise ResourceNotFoundException(f"Client with id {client_id} not found")
        return db_client

    async def update_client(
        self,
        client_id: int,
        client_update: schemas.ClientUpdate,
        *,
        current_user: models.User,
    ) -> models.Client:
        self.case_access.require_admin(current_user)
        client_logger = get_security_logger(
            admin_user_id=current_user.id,
            client_id=client_id,
            action="update_client",
            event_type="client_update_attempt",
        )

        try:
            db_client = self.db.get(models.Client, client_id)
            if not db_client:
                client_logger.bind(
                    event_type="client_update_failed", failure_reason="client_not_found"
                ).warning("Client update failed: client not found")
                raise ResourceNotFoundException(f"Client with id {client_id} not found")

            if client_update.email and client_update.email != db_client.email:
                existing = self.db.exec(
                    select(models.Client).where(
                        models.Client.email == client_update.email
                    )
                ).first()
                if existing:
                    client_logger.bind(
                        event_type="client_update_failed", failure_reason="email_taken"
                    ).warning("Client update failed: email already registered")
                    raise DuplicateResourceException("Email already registered")

            with transaction(self.db):
                update_data = client_update.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    setattr(db_client, field, value)
                db_client.updated_at = get_utc_now()
                self.db.add(db_client)
            self.db.refresh(db_client)
            updated_client = db_client

            client_logger.bind(
                client_name=updated_client.name, event_type="client_update_success"
            ).info("Client updated successfully")

            return updated_client

        except (DuplicateResourceException, ResourceNotFoundException):
            raise
        except Exception as e:
            client_logger.bind(
                event_type="client_update_error", error_type="system_error"
            ).error(f"Client update error: {e!s}")
            raise BaseException(f"Client update error: {e!s}")

    async def delete_client(self, client_id: int, *, current_user: models.User) -> None:
        self.case_access.require_admin(current_user)
        client_logger = get_security_logger(
            admin_user_id=current_user.id,
            client_id=client_id,
            action="delete_client",
            event_type="client_deletion_attempt",
        )

        try:
            db_client = self.db.get(models.Client, client_id)
            if not db_client:
                client_logger.bind(
                    event_type="client_deletion_failed",
                    failure_reason="client_not_found",
                ).warning("Client deletion failed: client not found")
                raise ResourceNotFoundException(f"Client with id {client_id} not found")

            cases_for_client = self.db.exec(
                select(models.Case).where(models.Case.client_id == client_id)
            ).all()

            if cases_for_client:
                client_logger.bind(
                    event_type="client_deletion_failed",
                    failure_reason="has_associated_cases",
                    case_count=len(cases_for_client),
                ).warning("Client deletion failed: client has associated cases")
                raise BaseException(
                    "Cannot delete client with associated cases. Please remove or reassign all cases first."
                )

            with transaction(self.db):
                self.db.delete(db_client)

            client_logger.bind(
                client_name=db_client.name, event_type="client_deletion_success"
            ).info("Client deleted successfully")

        except (ResourceNotFoundException, BaseException):
            raise
        except Exception as e:
            client_logger.bind(
                event_type="client_deletion_error", error_type="system_error"
            ).error(f"Client deletion error: {e!s}")
            raise BaseException(f"Client deletion error: {e!s}")
