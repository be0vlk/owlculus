"""
Authentication API
"""

from typing import Annotated

from app.core.exceptions import AuthenticationException, BaseException
from app.database.connection import get_db
from app.schemas.auth_schema import Token
from app.services.auth_service import AuthService
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
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
