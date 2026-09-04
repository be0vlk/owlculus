"""Session-backed invitation lifecycle and registration policy."""

import secrets
from datetime import UTC, timedelta
from enum import StrEnum

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from app import schemas
from app.core.exceptions import (
    BaseException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.logging import get_security_logger
from app.core.security import get_password_hash
from app.core.utils import get_utc_now
from app.database import models
from app.database.db_utils import transaction
from app.services.case_access import CaseAccess

TOKEN_LENGTH = 32
INVITE_EXPIRATION_HOURS = 48


class RegistrationConflict(StrEnum):
    USERNAME = "username"
    EMAIL = "email"


def _is_expired(invite: models.Invite) -> bool:
    return invite.expires_at.replace(tzinfo=UTC) <= get_utc_now()


def _validation_for(invite: models.Invite | None) -> schemas.InviteValidation:
    if invite is None:
        return schemas.InviteValidation(valid=False, error="Invalid invite token")
    if invite.used_at is not None:
        return schemas.InviteValidation(
            valid=False, error="Invite has already been used"
        )
    if _is_expired(invite):
        return schemas.InviteValidation(valid=False, error="Invite has expired")
    return schemas.InviteValidation(
        valid=True, role=invite.role, expires_at=invite.expires_at
    )


class InviteService:
    """Own invitation queries, writes, and registration rules."""

    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)

    def _find_by_token(self, token: str) -> models.Invite | None:
        return self.db.exec(
            select(models.Invite).where(models.Invite.token == token)
        ).first()

    def _registration_conflict(
        self, registration: schemas.UserRegistration
    ) -> RegistrationConflict | None:
        username_owner = self.db.exec(
            select(models.User).where(models.User.username == registration.username)
        ).first()
        if username_owner is not None:
            return RegistrationConflict.USERNAME
        email_owner = self.db.exec(
            select(models.User).where(models.User.email == registration.email)
        ).first()
        return RegistrationConflict.EMAIL if email_owner is not None else None

    @staticmethod
    def _duplicate_registration(
        conflict: RegistrationConflict,
    ) -> DuplicateResourceException:
        messages = {
            RegistrationConflict.USERNAME: "Username already taken",
            RegistrationConflict.EMAIL: "Email already registered",
        }
        return DuplicateResourceException(messages[conflict], field=conflict.value)

    async def create_invite(
        self, invite: schemas.InviteCreate, *, current_user: models.User
    ) -> models.Invite:
        self.case_access.require_admin(current_user)
        logger = get_security_logger(
            admin_user_id=current_user.id,
            action="create_invite",
            target_role=invite.role,
            event_type="invite_creation_attempt",
        )
        new_invite = models.Invite(
            token=secrets.token_urlsafe(TOKEN_LENGTH),
            role=invite.role,
            expires_at=get_utc_now() + timedelta(hours=INVITE_EXPIRATION_HOURS),
            created_by_id=current_user.id,
        )
        try:
            with transaction(self.db):
                self.db.add(new_invite)
                self.db.flush()
            self.db.refresh(new_invite)
        except Exception as error:
            logger.bind(
                event_type="invite_creation_error", error_type="system_error"
            ).error("Invite creation error")
            raise BaseException(str(error)) from error

        logger.bind(
            invite_id=new_invite.id,
            invite_role=new_invite.role,
            expires_at=new_invite.expires_at.isoformat(),
            event_type="invite_creation_success",
        ).info("Invite created successfully")
        return new_invite

    async def get_invites(
        self, skip: int = 0, limit: int = 100, *, current_user: models.User
    ) -> list[schemas.InviteListResponse]:
        self.case_access.require_admin(current_user)
        statement = (
            select(models.Invite)
            .options(selectinload(models.Invite.creator))  # type: ignore[arg-type]
            .order_by(col(models.Invite.created_at).desc())
            .offset(skip)
            .limit(limit)
        )
        invites = self.db.exec(statement).all()
        return [
            schemas.InviteListResponse(
                id=invite.id if invite.id is not None else 0,
                role=invite.role,
                created_at=invite.created_at,
                expires_at=invite.expires_at,
                used_at=invite.used_at,
                is_expired=_is_expired(invite),
                is_used=invite.used_at is not None,
                created_by_username=invite.creator.username,
            )
            for invite in invites
        ]

    async def validate_invite(self, token: str) -> schemas.InviteValidation:
        return _validation_for(self._find_by_token(token))

    async def register_user_with_invite(
        self, registration: schemas.UserRegistration
    ) -> schemas.UserRegistrationResponse:
        logger = get_security_logger(
            action="register_with_invite",
            username=registration.username,
            event_type="invite_registration_attempt",
        )
        invite = self._find_by_token(registration.token)
        validation = _validation_for(invite)
        if not validation.valid:
            logger.bind(
                event_type="invite_registration_failed",
                failure_reason="invalid_invite",
                validation_error=validation.error,
            ).warning("User registration failed: invalid invite")
            raise ValidationException(validation.error or "Invalid invite token")
        if invite is None:
            raise ResourceNotFoundException("Invalid invite token")

        conflict = self._registration_conflict(registration)
        if conflict is not None:
            raise self._duplicate_registration(conflict)

        user = models.User(
            username=registration.username,
            email=registration.email,
            password_hash=get_password_hash(registration.password),
            role=invite.role,
            is_superadmin=False,
        )
        try:
            with transaction(self.db):
                self.db.add(user)
                invite.used_at = get_utc_now()
                self.db.add(invite)
                self.db.flush()
        except IntegrityError as error:
            conflict = self._registration_conflict(registration)
            if conflict is not None:
                raise self._duplicate_registration(conflict) from error
            raise ValidationException("Invalid user registration") from error
        except BaseException:
            raise
        except Exception as error:
            logger.bind(
                event_type="invite_registration_error", error_type="system_error"
            ).error("User registration error")
            raise BaseException("Internal server error") from error

        self.db.refresh(user)
        logger.bind(
            event_type="invite_registration_success",
            user_id=user.id,
            invite_id=invite.id,
            user_role=user.role,
        ).info("User registered successfully with invite")
        return schemas.UserRegistrationResponse.model_validate(user)

    async def delete_invite(self, invite_id: int, *, current_user: models.User) -> bool:
        self.case_access.require_admin(current_user)
        logger = get_security_logger(
            admin_user_id=current_user.id,
            invite_id=invite_id,
            action="delete_invite",
            event_type="invite_deletion_attempt",
        )
        invite = self.db.get(models.Invite, invite_id)
        if invite is None:
            logger.bind(
                event_type="invite_deletion_failed", failure_reason="invite_not_found"
            ).warning("Invite deletion failed: invite not found")
            raise ResourceNotFoundException("Invite not found")
        if invite.used_at is not None:
            logger.bind(
                event_type="invite_deletion_failed",
                failure_reason="invite_already_used",
                used_at=invite.used_at.isoformat(),
            ).warning("Invite deletion failed: cannot delete used invite")
            raise ValidationException("Cannot delete used invite")

        with transaction(self.db):
            self.db.delete(invite)
        logger.bind(
            event_type="invite_deletion_success",
            invite_role=invite.role,
            original_creator_id=invite.created_by_id,
        ).info("Invite deleted successfully")
        return True

    async def cleanup_expired_invites(self, *, current_user: models.User) -> int:
        self.case_access.require_admin(current_user)
        expired_invites = self.db.exec(
            select(models.Invite).where(
                models.Invite.expires_at < get_utc_now(),
                col(models.Invite.used_at).is_(None),
            )
        ).all()
        with transaction(self.db):
            for invite in expired_invites:
                self.db.delete(invite)
        return len(expired_invites)
