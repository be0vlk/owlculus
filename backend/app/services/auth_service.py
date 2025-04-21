
from datetime import timedelta
from fastapi import HTTPException, status
from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.database import crud


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    async def authenticate_user(self, username: str, password: str) -> dict:
        """
        Authenticate a user and return an access token
        """
        user = await crud.get_user_by_username(self.db, username=username)
        if not user or not security.verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"Authorization": "Bearer"},
            )

        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = security.create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )

        return {"access_token": access_token, "token_type": "bearer"}