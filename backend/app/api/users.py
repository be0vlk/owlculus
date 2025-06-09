"""
User management API
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database.connection import get_db
from app.database import models
from app import schemas
from app.core.dependencies import get_current_active_user
from app.services.user_service import UserService

router = APIRouter()


@router.post("/", response_model=schemas.User)
async def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    user_service = UserService(db)
    return await user_service.create_user(user=user, current_user=current_user)


@router.get("/me", response_model=schemas.User)
async def read_self(current_user: models.User = Depends(get_current_active_user)):
    return current_user


@router.get("/", response_model=list[schemas.User])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    user_service = UserService(db)
    return await user_service.get_users(
        current_user=current_user, skip=skip, limit=limit
    )


@router.put("/{user_id}", response_model=schemas.User)
async def update_user(
    user_id: int,
    user: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    user_service = UserService(db)
    return await user_service.update_user(
        user_id=user_id, user_update=user, current_user=current_user
    )


@router.put("/me/password", response_model=schemas.User)
async def change_password(
    password_change: schemas.PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    user_service = UserService(db)
    return await user_service.change_password(
        user_id=current_user.id,
        current_password=password_change.current_password,
        new_password=password_change.new_password,
        current_user=current_user,
    )


@router.put("/{user_id}/password", response_model=schemas.User)
async def admin_reset_password(
    user_id: int,
    password_reset: schemas.AdminPasswordReset,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    user_service = UserService(db)
    return await user_service.admin_reset_password(
        user_id=user_id,
        new_password=password_reset.new_password,
        current_user=current_user,
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
):
    user_service = UserService(db)
    return await user_service.delete_user(
        user_id=user_id,
        current_user=current_user,
    )
