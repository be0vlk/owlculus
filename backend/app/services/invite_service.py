import secrets
from datetime import timedelta, timezone

from app import schemas
from app.core.dependencies import admin_only
from app.core.logging import get_security_logger
from app.core.utils import get_utc_now
from app.database import crud, models
from fastapi import HTTPException
from sqlmodel import Session


class InviteService:
    def __init__(self, db: Session):
        self.db = db

    @admin_only()
    async def create_invite(
        self, invite: schemas.InviteCreate, current_user: models.User
    ) -> models.Invite:
        invite_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="create_invite",
            target_role=invite.role,
            event_type="invite_creation_attempt",
        )

        try:
            token = secrets.token_urlsafe(32)
            expires_at = get_utc_now() + timedelta(hours=48)

            new_invite = await crud.create_invite(
                db=self.db,
                token=token,
                role=invite.role,
                expires_at=expires_at,
                created_by_id=current_user.id,
            )

            invite_logger.bind(
                invite_id=new_invite.id,
                invite_role=new_invite.role,
                expires_at=new_invite.expires_at.isoformat(),
                event_type="invite_creation_success",
            ).info("Invite created successfully")

            return new_invite

        except Exception as e:
            invite_logger.bind(
                event_type="invite_creation_error", error_type="system_error"
            ).error(f"Invite creation error: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))

    @admin_only()
    async def get_invites(
        self, current_user: models.User, skip: int = 0, limit: int = 100
    ) -> list[schemas.InviteListResponse]:
        invites = await crud.get_all_invites(self.db, skip=skip, limit=limit)

        now = get_utc_now()
        result = []

        for invite in invites:
            result.append(
                schemas.InviteListResponse(
                    id=invite.id,
                    role=invite.role,
                    created_at=invite.created_at,
                    expires_at=invite.expires_at,
                    used_at=invite.used_at,
                    is_expired=invite.expires_at.replace(tzinfo=timezone.utc) < now,
                    is_used=invite.used_at is not None,
                )
            )

        return result

    async def validate_invite(self, token: str) -> schemas.InviteValidation:
        invite = await crud.get_invite_by_token(self.db, token=token)

        if not invite:
            return schemas.InviteValidation(valid=False, error="Invalid invite token")

        if invite.used_at:
            return schemas.InviteValidation(
                valid=False, error="Invite has already been used"
            )

        now = get_utc_now()
        if invite.expires_at.replace(tzinfo=timezone.utc) < now:
            return schemas.InviteValidation(valid=False, error="Invite has expired")

        return schemas.InviteValidation(
            valid=True,
            role=invite.role,
            expires_at=invite.expires_at,
        )

    async def register_user_with_invite(
        self, registration: schemas.UserRegistration
    ) -> schemas.UserRegistrationResponse:
        invite_logger = get_security_logger(
            action="register_with_invite",
            username=registration.username,
            event_type="invite_registration_attempt",
        )

        try:
            validation = await self.validate_invite(registration.token)
            if not validation.valid:
                invite_logger.bind(
                    event_type="invite_registration_failed",
                    failure_reason="invalid_invite",
                    validation_error=validation.error,
                ).warning("User registration failed: invalid invite")
                raise HTTPException(status_code=400, detail=validation.error)

            invite = await crud.get_invite_by_token(self.db, token=registration.token)
            if not invite:
                invite_logger.bind(
                    event_type="invite_registration_failed",
                    failure_reason="invite_not_found",
                ).warning("User registration failed: invite not found")
                raise HTTPException(status_code=400, detail="Invalid invite token")

            existing_user = await crud.get_user_by_username(
                self.db, username=registration.username
            )
            if existing_user:
                invite_logger.bind(
                    event_type="invite_registration_failed",
                    failure_reason="username_taken",
                ).warning("User registration failed: username already taken")
                raise HTTPException(status_code=400, detail="Username already taken")

            existing_user = await crud.get_user_by_email(
                self.db, email=registration.email
            )
            if existing_user:
                invite_logger.bind(
                    event_type="invite_registration_failed",
                    failure_reason="email_taken",
                ).warning("User registration failed: email already registered")
                raise HTTPException(status_code=400, detail="Email already registered")

            user = await crud.create_user_from_invite(
                db=self.db,
                username=registration.username,
                email=registration.email,
                password=registration.password,
                role=invite.role,
            )

            await crud.mark_invite_used(self.db, invite)

            invite_logger.bind(
                user_id=user.id,
                invite_id=invite.id,
                user_role=user.role,
                event_type="invite_registration_success",
            ).info("User registered successfully with invite")

            return schemas.UserRegistrationResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                role=user.role,
                created_at=user.created_at,
            )

        except HTTPException:
            raise
        except ValueError as e:
            invite_logger.bind(
                event_type="invite_registration_failed",
                failure_reason="validation_error",
            ).warning(f"User registration failed: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            invite_logger.bind(
                event_type="invite_registration_error", error_type="system_error"
            ).error(f"User registration error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @admin_only()
    async def delete_invite(self, invite_id: int, current_user: models.User) -> bool:
        invite_logger = get_security_logger(
            admin_user_id=current_user.id,
            invite_id=invite_id,
            action="delete_invite",
            event_type="invite_deletion_attempt",
        )

        try:
            invite = self.db.get(models.Invite, invite_id)
            if not invite:
                invite_logger.bind(
                    event_type="invite_deletion_failed",
                    failure_reason="invite_not_found",
                ).warning("Invite deletion failed: invite not found")
                raise HTTPException(status_code=404, detail="Invite not found")

            if invite.used_at:
                invite_logger.bind(
                    event_type="invite_deletion_failed",
                    failure_reason="invite_already_used",
                    used_at=invite.used_at.isoformat(),
                ).warning("Invite deletion failed: cannot delete used invite")
                raise HTTPException(status_code=400, detail="Cannot delete used invite")

            result = await crud.delete_invite(self.db, invite_id=invite_id)

            invite_logger.bind(
                invite_role=invite.role,
                original_creator_id=invite.created_by_id,
                event_type="invite_deletion_success",
            ).info("Invite deleted successfully")

            return result

        except HTTPException:
            raise
        except ValueError as e:
            invite_logger.bind(
                event_type="invite_deletion_failed", failure_reason="validation_error"
            ).warning(f"Invite deletion failed: {str(e)}")
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            invite_logger.bind(
                event_type="invite_deletion_error", error_type="system_error"
            ).error(f"Invite deletion error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @admin_only()
    async def cleanup_expired_invites(self, current_user: models.User) -> int:
        return await crud.delete_expired_invites(self.db)
