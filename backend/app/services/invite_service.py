import secrets
from datetime import timedelta, timezone
from sqlmodel import Session
from fastapi import HTTPException

from app.database import models, crud
from app import schemas
from app.core.dependencies import admin_only
from app.core.utils import get_utc_now


class InviteService:
    def __init__(self, db: Session):
        self.db = db

    @admin_only()
    async def create_invite(
        self, invite: schemas.InviteCreate, current_user: models.User
    ) -> models.Invite:
        # Generate secure token
        token = secrets.token_urlsafe(32)

        # Set expiration to 48 hours from now
        expires_at = get_utc_now() + timedelta(hours=48)

        try:
            return await crud.create_invite(
                db=self.db,
                token=token,
                role=invite.role,
                expires_at=expires_at,
                created_by_id=current_user.id,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @admin_only()
    async def get_invites(
        self, current_user: models.User, skip: int = 0, limit: int = 100
    ) -> list[schemas.InviteListResponse]:
        invites = await crud.get_invites_by_creator(
            self.db, creator_id=current_user.id, skip=skip, limit=limit
        )

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
        # Validate invite first
        validation = await self.validate_invite(registration.token)
        if not validation.valid:
            raise HTTPException(status_code=400, detail=validation.error)

        # Get the invite
        invite = await crud.get_invite_by_token(self.db, token=registration.token)
        if not invite:
            raise HTTPException(status_code=400, detail="Invalid invite token")

        # Check for existing username
        existing_user = await crud.get_user_by_username(
            self.db, username=registration.username
        )
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already taken")

        # Check for existing email
        existing_user = await crud.get_user_by_email(self.db, email=registration.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        try:
            # Create user with role from invite
            user = await crud.create_user_from_invite(
                db=self.db,
                username=registration.username,
                email=registration.email,
                password=registration.password,
                role=invite.role,
            )

            # Mark invite as used
            await crud.mark_invite_used(self.db, invite)

            return schemas.UserRegistrationResponse(
                id=user.id,
                username=user.username,
                email=user.email,
                role=user.role,
                created_at=user.created_at,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @admin_only()
    async def delete_invite(self, invite_id: int, current_user: models.User) -> bool:
        # Get invite to check ownership
        invite = self.db.get(models.Invite, invite_id)
        if not invite:
            raise HTTPException(status_code=404, detail="Invite not found")

        if invite.created_by_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Not authorized to delete this invite"
            )

        if invite.used_at:
            raise HTTPException(status_code=400, detail="Cannot delete used invite")

        try:
            return await crud.delete_invite(self.db, invite_id=invite_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @admin_only()
    async def cleanup_expired_invites(self, current_user: models.User) -> int:
        return await crud.delete_expired_invites(self.db)
