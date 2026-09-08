"""
Authentication API for Owlculus OSINT Platform.

This module provides JWT-based authentication endpoints for the Owlculus platform,
enabling secure access to digital investigation tools and case management features.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Session

from app.core.dependencies import get_client_ip, get_current_user
from app.core.login_rate_limiting import RedisLoginRateLimiter, get_login_rate_limiter
from app.core.setup import is_setup_required
from app.database import models
from app.database.connection import get_db
from app.schemas.auth_schema import SetupStatus, Token, WebSocketToken
from app.services.auth_service import AuthService

router = APIRouter()


@router.get("/setup-status", response_model=SetupStatus)
def get_setup_status(db: Annotated[Session, Depends(get_db)]) -> SetupStatus:
    """Report whether this installation still needs its first user."""
    return SetupStatus(setup_required=is_setup_required(db))


@router.post("/login", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
    limiter: Annotated[RedisLoginRateLimiter, Depends(get_login_rate_limiter)],
):
    await limiter.check(get_client_ip(request), form_data.username)
    auth_service = AuthService(db)
    return await auth_service.authenticate_user(
        username=form_data.username, password=form_data.password
    )


class WebSocketTokenRequest(BaseModel):
    execution_id: int
    kind: Literal["hunt", "plugin"] = "hunt"


@router.post("/websocket-token", response_model=WebSocketToken)
async def create_websocket_token(
    request: WebSocketTokenRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> WebSocketToken:
    """
    Create a single-use ephemeral token for WebSocket authentication

    This token is valid for 30 seconds and can only be used once
    to establish a WebSocket connection for the specified execution.
    """
    auth_service = AuthService(db)
    return await auth_service.create_websocket_token(
        request.execution_id, current_user, request.kind
    )
