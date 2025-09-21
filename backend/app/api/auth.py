"""
Authentication API for Owlculus OSINT Platform.

This module provides JWT-based authentication endpoints for the Owlculus platform,
enabling secure access to digital investigation tools and case management features.
"""

from typing import Annotated

from app.core.dependencies import get_current_user
from app.core.exceptions import (
	AuthenticationException,
	BaseException,
	AuthorizationException,
	ResourceNotFoundException,
)
from app.database import models
from app.database.connection import get_db
from app.schemas.auth_schema import Token
from app.services.auth_service import AuthService
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Session

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    try:
        return await auth_service.authenticate_user(
            username=form_data.username, password=form_data.password
        )
    except AuthenticationException as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


class WebSocketTokenRequest(BaseModel):
    execution_id: int


@router.post("/websocket-token")
async def create_websocket_token(
    request: WebSocketTokenRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a single-use ephemeral token for WebSocket authentication

    This token is valid for 30 seconds and can only be used once
    to establish a WebSocket connection for the specified execution.
    """
    auth_service = AuthService(db)
    try:
        return await auth_service.create_websocket_token(
            request.execution_id, current_user
        )
    except ResourceNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except AuthorizationException as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except BaseException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
