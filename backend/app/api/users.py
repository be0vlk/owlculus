"""
User Management API for Owlculus OSINT Platform.

This module provides comprehensive user account management for the Owlculus platform,
supporting role-based access control and secure user administration for investigation teams.

Key features include:
- User account CRUD operations with admin-level controls
- Role-based permission management (Admin, Manager, Investigator, Viewer)
- Secure password management with self-service and admin reset capabilities
- User profile management with investigation team integration
- Multi-level access controls ensuring proper separation of duties
- Account lifecycle management supporting team member onboarding and offboarding
"""

from app import schemas
from app.core.dependencies import admin_only, get_current_user
from app.core.exceptions import (
    AuthorizationException,
    BaseException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.database import models
from app.database.connection import get_db
from app.services.user_service import UserService
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

router = APIRouter()


@router.post("/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
@admin_only()
async def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_service = UserService(db)
    try:
        return await user_service.create_user(user=user, current_user=current_user)
    except DuplicateResourceException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/me", response_model=schemas.User)
async def read_self(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.get("/", response_model=list[schemas.User])
@admin_only()
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_service = UserService(db)
    try:
        return await user_service.get_users(
            current_user=current_user, skip=skip, limit=limit
        )
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{user_id}", response_model=schemas.User)
async def update_user(
    user_id: int,
    user: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_service = UserService(db)
    try:
        return await user_service.update_user(
            user_id=user_id, user_update=user, current_user=current_user
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DuplicateResourceException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/me/password", response_model=schemas.User)
async def change_password(
    password_change: schemas.PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_service = UserService(db)
    try:
        return await user_service.change_password(
            user_id=current_user.id,
            current_password=password_change.current_password,
            new_password=password_change.new_password,
            current_user=current_user,
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValidationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{user_id}/password", response_model=schemas.User)
@admin_only()
async def admin_reset_password(
    user_id: int,
    password_reset: schemas.AdminPasswordReset,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_service = UserService(db)
    try:
        return await user_service.admin_reset_password(
            user_id=user_id,
            new_password=password_reset.new_password,
            current_user=current_user,
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@admin_only()
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_service = UserService(db)
    try:
        return await user_service.delete_user(
            user_id=user_id,
            current_user=current_user,
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except AuthorizationException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
