from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database.connection import get_db
from app.database import models
from app import schemas
from app.core.dependencies import get_current_active_user
from app.services.invite_service import InviteService

router = APIRouter()


@router.post("/", response_model=schemas.InviteResponse)
async def create_invite(
    invite: schemas.InviteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    invite_service = InviteService(db)
    return await invite_service.create_invite(invite=invite, current_user=current_user)


@router.get("/", response_model=list[schemas.InviteListResponse])
async def get_invites(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    invite_service = InviteService(db)
    return await invite_service.get_invites(
        current_user=current_user, skip=skip, limit=limit
    )


@router.get("/{token}/validate", response_model=schemas.InviteValidation)
async def validate_invite(
    token: str,
    db: Session = Depends(get_db),
):
    invite_service = InviteService(db)
    return await invite_service.validate_invite(token=token)


@router.post("/{token}/register", response_model=schemas.UserRegistrationResponse)
async def register_user(
    token: str,
    registration_data: schemas.UserRegistration,
    db: Session = Depends(get_db),
):
    # Ensure token in URL matches token in body
    if token != registration_data.token:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Token mismatch")

    invite_service = InviteService(db)
    return await invite_service.register_user_with_invite(
        registration=registration_data
    )


@router.delete("/{invite_id}")
async def delete_invite(
    invite_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    invite_service = InviteService(db)
    await invite_service.delete_invite(invite_id=invite_id, current_user=current_user)
    return {"message": "Invite deleted successfully"}


@router.post("/cleanup")
async def cleanup_expired_invites(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    invite_service = InviteService(db)
    count = await invite_service.cleanup_expired_invites(current_user=current_user)
    return {"message": f"Cleaned up {count} expired invites"}
