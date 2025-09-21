"""
Business logic for user invitation management.

This module handles invite creation, validation, expiration, and acceptance workflows.
Provides comprehensive invitation system with security logging, token generation,
and user registration through invitation tokens.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Protocol

from app import schemas
from app.core.exceptions import (
	BaseException,
	DuplicateResourceException,
	ResourceNotFoundException,
)
from app.core.logging import get_security_logger
from app.core.utils import get_utc_now
from app.database import crud, models
from sqlmodel import Session

TOKEN_LENGTH = 32
INVITE_EXPIRATION_HOURS = 48
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 50
MIN_PASSWORD_LENGTH = 8


class InviteException(BaseException):
    """Base exception for invite-related errors"""

    pass


class InvalidInviteException(InviteException):
    """Raised when an invite is invalid, expired, or already used"""

    pass


class InviteRegistrationException(InviteException):
    """Raised when user registration with invite fails"""

    pass


class InviteRepository(Protocol):
    """Protocol for invite data access operations"""

    async def create_invite(
        self, db: Session, token: str, role: str, expires_at, created_by_id: int
    ) -> models.Invite: ...

    async def get_all_invites(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> list[models.Invite]: ...

    async def get_invite_by_token(
        self, db: Session, token: str
    ) -> Optional[models.Invite]: ...

    async def mark_invite_used(self, db: Session, invite: models.Invite) -> None: ...

    async def delete_invite(self, db: Session, invite_id: int) -> bool: ...

    async def delete_expired_invites(self, db: Session) -> int: ...


class UserRepository(Protocol):
    """Protocol for user data access operations"""

    async def get_user_by_username(
        self, db: Session, username: str
    ) -> Optional[models.User]: ...

    async def get_user_by_email(
        self, db: Session, email: str
    ) -> Optional[models.User]: ...

    async def create_user_from_invite(
        self, db: Session, username: str, email: str, password: str, role: str
    ) -> models.User: ...


@dataclass
class InviteValidationResult:
    valid: bool
    role: Optional[str] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None


class SecurityLogger:
    """Wrapper for security logging with consistent formatting"""

    def __init__(self, base_context: dict):
        self._base_context = base_context
        self._logger = get_security_logger(**base_context)

    def log_success(self, event_type: str, message: str, **extra_context):
        self._logger.bind(event_type=event_type, **extra_context).info(message)

    def log_failure(
        self, event_type: str, message: str, failure_reason: str, **extra_context
    ):
        self._logger.bind(
            event_type=event_type, failure_reason=failure_reason, **extra_context
        ).warning(message)

    def log_error(
        self, event_type: str, message: str, error: Exception, **extra_context
    ):
        self._logger.bind(
            event_type=event_type, error_type="system_error", **extra_context
        ).error(f"{message}: {str(error)}")


class InviteValidator:
    """Handles invite validation logic"""

    def validate_token(self, invite: Optional[models.Invite]) -> InviteValidationResult:
        if not invite:
            return InviteValidationResult(valid=False, error="Invalid invite token")

        if invite.used_at:
            return InviteValidationResult(
                valid=False, error="Invite has already been used"
            )

        if self._is_expired(invite):
            return InviteValidationResult(valid=False, error="Invite has expired")

        return InviteValidationResult(
            valid=True, role=invite.role, expires_at=invite.expires_at
        )

    def _is_expired(self, invite: models.Invite) -> bool:
        now = get_utc_now()
        return invite.expires_at.replace(tzinfo=timezone.utc) <= now


class UserValidator:
    """Handles user validation during registration"""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def validate_registration(
        self, db: Session, username: str, email: str
    ) -> Optional[str]:
        if await self.user_repo.get_user_by_username(db, username):
            return "Username already taken"

        if await self.user_repo.get_user_by_email(db, email):
            return "Email already registered"

        return None


class InviteService:
    """Service for managing invites with improved structure"""

    def __init__(
        self,
        db: Session,
        invite_repo: Optional[InviteRepository] = None,
        user_repo: Optional[UserRepository] = None,
    ):
        self.db = db
        self.invite_repo = invite_repo or crud
        self.user_repo = user_repo or crud
        self.validator = InviteValidator()
        self.user_validator = UserValidator(self.user_repo)

    async def create_invite(
        self, invite: schemas.InviteCreate, *, current_user: models.User
    ) -> models.Invite:
        logger = SecurityLogger(
            {
                "admin_user_id": current_user.id,
                "action": "create_invite",
                "target_role": invite.role,
            }
        )

        try:
            token = self._generate_secure_token()
            expires_at = self._calculate_expiration()

            new_invite = await self.invite_repo.create_invite(
                db=self.db,
                token=token,
                role=invite.role,
                expires_at=expires_at,
                created_by_id=current_user.id,
            )

            logger.log_success(
                "invite_creation_success",
                "Invite created successfully",
                invite_id=new_invite.id,
                invite_role=new_invite.role,
                expires_at=new_invite.expires_at.isoformat(),
            )

            return new_invite

        except Exception as e:
            logger.log_error("invite_creation_error", "Invite creation error", e)
            raise InviteException(str(e))

    async def get_invites(
        self, skip: int = 0, limit: int = 100, *, current_user: models.User
    ) -> list[schemas.InviteListResponse]:
        invites = await self.invite_repo.get_all_invites(
            self.db, skip=skip, limit=limit
        )
        return [self._map_invite_to_response(invite) for invite in invites]

    async def validate_invite(self, token: str) -> schemas.InviteValidation:
        invite = await self.invite_repo.get_invite_by_token(self.db, token=token)
        result = self.validator.validate_token(invite)

        return schemas.InviteValidation(
            valid=result.valid,
            role=result.role,
            expires_at=result.expires_at,
            error=result.error,
        )

    async def register_user_with_invite(
        self, registration: schemas.UserRegistration
    ) -> schemas.UserRegistrationResponse:
        logger = SecurityLogger(
            {
                "action": "register_with_invite",
                "username": registration.username,
            }
        )

        try:
            invite = await self._validate_and_get_invite(registration.token, logger)

            await self._validate_user_registration(
                registration.username, registration.email, logger
            )

            user = await self._create_user_from_registration(
                registration, invite, logger
            )

            await self.invite_repo.mark_invite_used(self.db, invite)

            logger.log_success(
                "invite_registration_success",
                "User registered successfully with invite",
                user_id=user.id,
                invite_id=invite.id,
                user_role=user.role,
            )

            return self._map_user_to_response(user)

        except (BaseException, ResourceNotFoundException, DuplicateResourceException):
            raise
        except ValueError as e:
            logger.log_failure(
                "invite_registration_failed",
                "User registration failed",
                "validation_error",
            )
            raise InviteRegistrationException(str(e))
        except Exception as e:
            logger.log_error("invite_registration_error", "User registration error", e)
            raise InviteException("Internal server error")

    async def delete_invite(self, invite_id: int, *, current_user: models.User) -> bool:
        logger = SecurityLogger(
            {
                "admin_user_id": current_user.id,
                "invite_id": invite_id,
                "action": "delete_invite",
            }
        )

        try:
            invite = await self._get_invite_by_id(invite_id, logger)
            self._validate_invite_deletion(invite, logger)

            result = await self.invite_repo.delete_invite(self.db, invite_id=invite_id)

            logger.log_success(
                "invite_deletion_success",
                "Invite deleted successfully",
                invite_role=invite.role,
                original_creator_id=invite.created_by_id,
            )

            return result

        except (BaseException, ResourceNotFoundException):
            raise
        except Exception as e:
            logger.log_error("invite_deletion_error", "Invite deletion error", e)
            raise InviteException("Internal server error")

    async def cleanup_expired_invites(self, *, current_user: models.User) -> int:
        return await self.invite_repo.delete_expired_invites(self.db)

    def _generate_secure_token(self) -> str:
        return secrets.token_urlsafe(TOKEN_LENGTH)

    def _calculate_expiration(self) -> datetime:
        return get_utc_now() + timedelta(hours=INVITE_EXPIRATION_HOURS)

    def _map_invite_to_response(
        self, invite: models.Invite
    ) -> schemas.InviteListResponse:
        now = get_utc_now()
        return schemas.InviteListResponse(
            id=invite.id,
            role=invite.role,
            created_at=invite.created_at,
            expires_at=invite.expires_at,
            used_at=invite.used_at,
            is_expired=invite.expires_at.replace(tzinfo=timezone.utc) <= now,
            is_used=invite.used_at is not None,
        )

    def _map_user_to_response(
        self, user: models.User
    ) -> schemas.UserRegistrationResponse:
        return schemas.UserRegistrationResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            role=user.role,
            created_at=user.created_at,
        )

    async def _validate_and_get_invite(
        self, token: str, logger: SecurityLogger
    ) -> models.Invite:
        validation = await self.validate_invite(token)
        if not validation.valid:
            logger.log_failure(
                "invite_registration_failed",
                "User registration failed: invalid invite",
                "invalid_invite",
                validation_error=validation.error,
            )
            raise InvalidInviteException(validation.error)

        invite = await self.invite_repo.get_invite_by_token(self.db, token=token)
        if not invite:
            logger.log_failure(
                "invite_registration_failed",
                "User registration failed: invite not found",
                "invite_not_found",
            )
            raise ResourceNotFoundException("Invalid invite token")

        return invite

    async def _validate_user_registration(
        self, username: str, email: str, logger: SecurityLogger
    ) -> None:
        error = await self.user_validator.validate_registration(
            self.db, username, email
        )
        if error:
            logger.log_failure(
                "invite_registration_failed",
                f"User registration failed: {error}",
                error.lower().replace(" ", "_"),
            )
            raise DuplicateResourceException(error)

    async def _create_user_from_registration(
        self,
        registration: schemas.UserRegistration,
        invite: models.Invite,
        logger: SecurityLogger,
    ) -> models.User:
        return await self.user_repo.create_user_from_invite(
            db=self.db,
            username=registration.username,
            email=registration.email,
            password=registration.password,
            role=invite.role,
        )

    async def _get_invite_by_id(
        self, invite_id: int, logger: SecurityLogger
    ) -> models.Invite:
        invite = self.db.get(models.Invite, invite_id)
        if not invite:
            logger.log_failure(
                "invite_deletion_failed",
                "Invite deletion failed: invite not found",
                "invite_not_found",
            )
            raise ResourceNotFoundException("Invite not found")
        return invite

    def _validate_invite_deletion(
        self, invite: models.Invite, logger: SecurityLogger
    ) -> None:
        if invite.used_at:
            logger.log_failure(
                "invite_deletion_failed",
                "Invite deletion failed: cannot delete used invite",
                "invite_already_used",
                used_at=invite.used_at.isoformat(),
            )
            raise InviteException("Cannot delete used invite")
