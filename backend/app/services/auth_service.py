"""
Authentication service handling all auth-related business logic
"""

from datetime import timedelta

from app.core import security
from app.core.config import settings
from app.core.exceptions import AuthenticationException, BaseException
from app.core.logging import get_security_logger
from app.database import crud
from sqlmodel import Session


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    async def authenticate_user(self, username: str, password: str) -> dict:
        """
        Authenticate a user and return an access token
        """
        auth_logger = get_security_logger(
            username=username, action="authenticate", event_type="login_attempt"
        )
        auth_logger.info("Authentication attempt started")

        try:
            user = await crud.get_user_by_username(self.db, username=username)
            if not user:
                auth_logger.warning(
                    "Authentication failed: user not found",
                    event_type="login_failed",
                    failure_reason="user_not_found",
                )
                raise AuthenticationException("Incorrect username or password")

            if not security.verify_password(password, user.password_hash):
                auth_logger.bind(
                    user_id=user.id,
                    event_type="login_failed",
                    failure_reason="invalid_password",
                ).warning("Authentication failed: invalid password")
                raise AuthenticationException("Incorrect username or password")

            access_token_expires = timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
            access_token = security.create_access_token(
                data={"sub": user.username}, expires_delta=access_token_expires
            )

            auth_logger.bind(
                user_id=user.id, role=user.role, event_type="login_success"
            ).info("Authentication successful")

            return {"access_token": access_token, "token_type": "bearer"}

        except AuthenticationException:
            raise
        except Exception as e:
            auth_logger.error(
                f"Authentication error: {str(e)}",
                event_type="login_error",
                error_type="system_error",
            )
            raise BaseException("Authentication service error")
