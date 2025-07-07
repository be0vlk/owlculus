"""
Authentication service handling all auth-related business logic
"""

from datetime import timedelta

from app.core import security
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    BaseException,
    AuthorizationException,
    ResourceNotFoundException,
)
from app.core.logging import get_security_logger
from app.database import crud
from app.database.models import User, HuntExecution
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

    async def create_websocket_token(
        self, execution_id: int, current_user: User
    ) -> dict:
        """
        Create a single-use ephemeral token for WebSocket authentication

        Args:
            execution_id: The hunt execution ID
            current_user: The authenticated user

        Returns:
            Dict containing the token, execution_id, and expiration time
        """
        auth_logger = get_security_logger(
            user_id=current_user.id,
            username=current_user.username,
            action="create_websocket_token",
            execution_id=execution_id,
        )

        try:
            # Get the execution
            execution = self.db.get(HuntExecution, execution_id)
            if not execution:
                auth_logger.warning(
                    "WebSocket token creation failed: execution not found",
                    event_type="ws_token_failed",
                    failure_reason="execution_not_found",
                )
                raise ResourceNotFoundException("Execution not found")

            # Check if user has access to the case
            from app.core.dependencies import check_case_access

            try:
                check_case_access(self.db, execution.case_id, current_user)
            except Exception:
                auth_logger.warning(
                    "WebSocket token creation failed: access denied",
                    event_type="ws_token_failed",
                    failure_reason="access_denied",
                    case_id=execution.case_id,
                )
                raise AuthorizationException("Access denied")

            # Create ephemeral token
            token = security.ephemeral_token_manager.create_token(
                current_user.id, execution_id
            )

            auth_logger.info(
                "WebSocket token created successfully",
                event_type="ws_token_created",
                case_id=execution.case_id,
            )

            return {
                "token": token,
                "execution_id": execution_id,
                "expires_in": security.ephemeral_token_manager.token_ttl,
            }

        except (ResourceNotFoundException, AuthorizationException):
            raise
        except Exception as e:
            auth_logger.error(
                f"WebSocket token creation error: {str(e)}",
                event_type="ws_token_error",
                error_type="system_error",
            )
            raise BaseException("WebSocket token service error")
