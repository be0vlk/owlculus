"""Session-backed invitation lifecycle and registration policy."""

import secrets
from datetime import UTC, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from app import schemas
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.core.logging import audit_operation
from app.core.security import get_password_hash
from app.core.utils import get_utc_now
from app.database import models
from app.database.db_utils import transaction
from app.services.case_access import CaseAccess
from app.services.user_service import duplicate_user_error

TOKEN_LENGTH = 32
INVITE_EXPIRATION_HOURS = 48


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

    @audit_operation("invite_creation")
    async def create_invite(
        self, invite: schemas.InviteCreate, *, current_user: models.User
    ) -> models.Invite:
        self.case_access.require_admin(current_user)
        new_invite = models.Invite(
            token=secrets.token_urlsafe(TOKEN_LENGTH),
            role=invite.role,
            expires_at=get_utc_now() + timedelta(hours=INVITE_EXPIRATION_HOURS),
            created_by_id=current_user.id,
        )
        with transaction(self.db):
            self.db.add(new_invite)
            self.db.flush()
        self.db.refresh(new_invite)
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

    @audit_operation("invite_registration")
    async def register_user_with_invite(
        self, registration: schemas.UserRegistration
    ) -> schemas.UserRegistrationResponse:
        invite = self._find_by_token(registration.token)
        validation = _validation_for(invite)
        if not validation.valid:
            raise ValidationException(validation.error or "Invalid invite token")
        if invite is None:
            raise ResourceNotFoundException("Invalid invite token")

        duplicate = duplicate_user_error(
            self.db, registration.username, registration.email
        )
        if duplicate:
            raise duplicate

        user = models.User(
            username=registration.username,
            email=registration.email,
            password_hash=get_password_hash(registration.password),
            role=invite.role,
            is_superadmin=False,
        )
        try:
            with transaction(self.db):
                # Refresh even an already-loaded invite after acquiring the lock.
                # Check wall-clock expiry here, after any competing transaction.
                invite = self.db.exec(
                    select(models.Invite)
                    .where(models.Invite.token == registration.token)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                ).first()
                validation = _validation_for(invite)
                if not validation.valid or invite is None:
                    raise ValidationException(
                        validation.error or "Invalid invite token"
                    )
                user.role = invite.role
                self.db.add(user)
                invite.used_at = get_utc_now()
                self.db.add(invite)
                self.db.flush()
        except IntegrityError as error:
            duplicate = duplicate_user_error(
                self.db, registration.username, registration.email
            )
            if duplicate:
                raise duplicate from error
            raise ValidationException("Invalid user registration") from error

        self.db.refresh(user)
        return schemas.UserRegistrationResponse.model_validate(user)

    @audit_operation("invite_deletion")
    async def delete_invite(self, invite_id: int, *, current_user: models.User) -> bool:
        self.case_access.require_admin(current_user)
        invite = self.db.get(models.Invite, invite_id)
        if invite is None:
            raise ResourceNotFoundException("Invite not found")
        if invite.used_at is not None:
            raise ValidationException("Cannot delete used invite")

        with transaction(self.db):
            self.db.delete(invite)
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
