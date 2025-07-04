from app import schemas
from app.core.dependencies import get_current_user
from app.database import models
from app.database.connection import get_db
from app.services.invite_service import InviteService
from fastapi import APIRouter, Depends, status
from sqlmodel import Session

router = APIRouter()


@router.post(
    "/", response_model=schemas.InviteResponse, status_code=status.HTTP_201_CREATED
)
async def create_invite(
    invite: schemas.InviteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    invite_service = InviteService(db)
    return await invite_service.create_invite(invite=invite, current_user=current_user)


@router.get("/", response_model=list[schemas.InviteListResponse])
async def get_invites(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    invite_service = InviteService(db)
    return await invite_service.get_invites(
        current_user=current_user, skip=skip, limit=limit
    )


@router.post("/validate", response_model=schemas.InviteValidation)
async def validate_invite(
    token_data: schemas.InviteTokenValidation,
    db: Session = Depends(get_db),
):
    invite_service = InviteService(db)
    return await invite_service.validate_invite(token=token_data.token)


@router.post(
    "/register",
    response_model=schemas.UserRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    registration_data: schemas.UserRegistration,
    db: Session = Depends(get_db),
):
    invite_service = InviteService(db)
    return await invite_service.register_user_with_invite(
        registration=registration_data
    )


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invite(
    invite_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    invite_service = InviteService(db)
    await invite_service.delete_invite(invite_id=invite_id, current_user=current_user)
    return {"message": "Invite deleted successfully"}


@router.post("/cleanup")
async def cleanup_expired_invites(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    invite_service = InviteService(db)
    count = await invite_service.cleanup_expired_invites(current_user=current_user)
    return {"message": f"Cleaned up {count} expired invites"}
