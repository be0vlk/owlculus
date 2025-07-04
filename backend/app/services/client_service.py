"""
Client service layer handling all client-related business logic
"""

from app import schemas
from app.core.exceptions import (
    DuplicateResourceException,
    ResourceNotFoundException,
    BaseException,
)
from app.core.logging import get_security_logger
from app.database import crud, models
from sqlmodel import Session


class ClientService:
    def __init__(self, db: Session):
        self.db = db

    async def get_clients(
        self, skip: int = 0, limit: int = 100, *, current_user: models.User
    ) -> list[models.Client]:
        if skip < 0 or limit < 0:
            raise ValueError("Skip and limit must be non-negative")
        return await crud.get_clients(self.db, skip=skip, limit=limit)

    async def create_client(
        self, client: schemas.ClientCreate, *, current_user: models.User
    ) -> models.Client:
        client_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="create_client",
            client_name=client.name,
            event_type="client_creation_attempt",
        )

        try:
            # Check for duplicate email
            existing = await crud.get_client_by_email(self.db, email=client.email)
            if existing:
                client_logger.bind(
                    event_type="client_creation_failed", failure_reason="email_exists"
                ).warning("Client creation failed: email already registered")
                raise DuplicateResourceException("Email already registered")

            new_client = await crud.create_client(self.db, client=client)

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
            ).error(f"Client creation error: {str(e)}")
            raise BaseException(f"Client creation error: {str(e)}")

    async def get_client(
        self, client_id: int, *, current_user: models.User
    ) -> models.Client:
        db_client = await crud.get_client(self.db, client_id=client_id)
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
        client_logger = get_security_logger(
            admin_user_id=current_user.id,
            client_id=client_id,
            action="update_client",
            event_type="client_update_attempt",
        )

        try:
            db_client = await crud.get_client(self.db, client_id=client_id)
            if not db_client:
                client_logger.bind(
                    event_type="client_update_failed", failure_reason="client_not_found"
                ).warning("Client update failed: client not found")
                raise ResourceNotFoundException(f"Client with id {client_id} not found")

            # Check email uniqueness if being updated
            if client_update.email and client_update.email != db_client.email:
                existing = await crud.get_client_by_email(
                    self.db, email=client_update.email
                )
                if existing:
                    client_logger.bind(
                        event_type="client_update_failed", failure_reason="email_taken"
                    ).warning("Client update failed: email already registered")
                    raise DuplicateResourceException("Email already registered")

            updated_client = await crud.update_client(
                self.db, client_id=client_id, client=client_update
            )

            client_logger.bind(
                client_name=updated_client.name, event_type="client_update_success"
            ).info("Client updated successfully")

            return updated_client

        except (DuplicateResourceException, ResourceNotFoundException):
            raise
        except Exception as e:
            client_logger.bind(
                event_type="client_update_error", error_type="system_error"
            ).error(f"Client update error: {str(e)}")
            raise BaseException(f"Client update error: {str(e)}")

    async def delete_client(self, client_id: int, *, current_user: models.User) -> None:
        client_logger = get_security_logger(
            admin_user_id=current_user.id,
            client_id=client_id,
            action="delete_client",
            event_type="client_deletion_attempt",
        )

        try:
            db_client = await crud.get_client(self.db, client_id=client_id)
            if not db_client:
                client_logger.bind(
                    event_type="client_deletion_failed",
                    failure_reason="client_not_found",
                ).warning("Client deletion failed: client not found")
                raise ResourceNotFoundException(f"Client with id {client_id} not found")

            # Check if client has any associated cases
            client_cases = await crud.get_cases(self.db)
            cases_for_client = [
                case for case in client_cases if case.client_id == client_id
            ]

            if cases_for_client:
                client_logger.bind(
                    event_type="client_deletion_failed",
                    failure_reason="has_associated_cases",
                    case_count=len(cases_for_client),
                ).warning("Client deletion failed: client has associated cases")
                raise BaseException(
                    "Cannot delete client with associated cases. Please remove or reassign all cases first."
                )

            await crud.delete_client(self.db, client_id=client_id)

            client_logger.bind(
                client_name=db_client.name, event_type="client_deletion_success"
            ).info("Client deleted successfully")

        except (ResourceNotFoundException, BaseException):
            raise
        except Exception as e:
            client_logger.bind(
                event_type="client_deletion_error", error_type="system_error"
            ).error(f"Client deletion error: {str(e)}")
            raise BaseException(f"Client deletion error: {str(e)}")
