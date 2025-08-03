"""
API endpoints for managing user invitations and account creation requests.

This module handles invite creation, retrieval, validation, acceptance, and deletion.
Provides endpoints for user registration through invitation tokens and administrative
invite management functionality.

Key features include:
- Secure invitation token generation and validation with expiration management
- Role-based invite creation with administrative access controls
- User registration workflow with invite token verification and account creation
- Comprehensive invite lifecycle management including cleanup of expired tokens
- Security logging and audit trail for all invitation-related operations
"""

from app import schemas
from app.core.dependencies import admin_only, get_current_user
from app.core.exceptions import (
    BaseException,
    DuplicateResourceException,
    ResourceNotFoundException,
)
from app.database import models
from app.database.connection import get_db
from app.services.invite_service import InviteService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

router = APIRouter()


@router.post(
    "/", response_model=schemas.InviteResponse, status_code=status.HTTP_201_CREATED
)
@admin_only()
async def create_invite(
    invite: schemas.InviteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    invite_service = InviteService(db)
    try:
        return await invite_service.create_invite(invite=invite, current_user=current_user)
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/", response_model=list[schemas.InviteListResponse])
@admin_only()
async def get_invites(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    invite_service = InviteService(db)
    try:
        return await invite_service.get_invites(
            skip=skip, limit=limit, current_user=current_user
        )
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
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
    try:
        return await invite_service.register_user_with_invite(
            registration=registration_data
        )
    except DuplicateResourceException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
@admin_only()
async def delete_invite(
    invite_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    invite_service = InviteService(db)
    try:
        await invite_service.delete_invite(invite_id=invite_id, current_user=current_user)
        return {"message": "Invite deleted successfully"}
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except BaseException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/cleanup")
@admin_only()
async def cleanup_expired_invites(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    invite_service = InviteService(db)
    try:
        count = await invite_service.cleanup_expired_invites(current_user=current_user)
        return {"message": f"Cleaned up {count} expired invites"}
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
