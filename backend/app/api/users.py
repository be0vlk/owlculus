"""
User Management API for Owlculus OSINT Platform.

This module provides comprehensive user account management for the Owlculus platform,
supporting role-based access control and secure user administration for investigation teams.
"""

from typing import Any

from fastapi import APIRouter, Body, Depends, Request, status
from sqlmodel import Session

from app import schemas
from app.core.dependencies import (
    get_client_ip,
    get_current_user,
    get_optional_current_user,
)
from app.core.exceptions import RateLimitException
from app.core.logging import get_security_logger
from app.core.rate_limiting import get_bootstrap_rate_limiter
from app.core.setup import is_setup_required
from app.database import models
from app.database.connection import get_db
from app.services.user_service import UserService

router = APIRouter()


@router.post("/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    user_data: Any = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User | None = Depends(get_optional_current_user),
):
    user_service = UserService(db)
    if current_user is None:
        if is_setup_required(db):
            client_address = get_client_ip(request)
            if not await get_bootstrap_rate_limiter(request).allow(client_address):
                get_security_logger(
                    action="create_user",
                    event_type="rate_limit_exceeded",
                    is_bootstrap=True,
                    client_ip=client_address,
                ).warning("Bootstrap user creation rate limit exceeded")
                raise RateLimitException(
                    "Too many setup attempts. Please try again later."
                )
        return await user_service.create_bootstrap_user(user_data=user_data)
    return await user_service.create_user_from_payload(user_data, current_user)


@router.get("/me", response_model=schemas.User)
async def read_self(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.get("/", response_model=list[schemas.User])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
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
    current_user: models.User = Depends(get_current_user),
):
    user_service = UserService(db)
    return await user_service.update_user(
        user_id=user_id, user_update=user, current_user=current_user
    )


@router.put("/me/password", response_model=schemas.User)
async def change_password(
    password_change: schemas.PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
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
    current_user: models.User = Depends(get_current_user),
):
    user_service = UserService(db)
    return await user_service.admin_reset_password(
        user_id=user_id,
        new_password=password_reset.new_password,
        current_user=current_user,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    user_service = UserService(db)
    return await user_service.delete_user(
        user_id=user_id,
        current_user=current_user,
    )
