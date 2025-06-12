"""
Authentication API
"""

from typing import Annotated

from app.database.connection import get_db
from app.schemas.auth_schema import Token
from app.services.auth_service import AuthService
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    auth_service = AuthService(db)
    return await auth_service.authenticate_user(
        username=form_data.username, password=form_data.password
    )
