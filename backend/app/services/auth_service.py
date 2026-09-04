"""Session-backed authentication and WebSocket-token operations."""

from datetime import timedelta

from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    ResourceNotFoundException,
)
from app.core.logging import get_security_logger
from app.database.models import HuntExecution, User
from app.schemas.auth_schema import Token, WebSocketToken
from app.services.case_access import CaseAccess

TOKEN_TYPE_BEARER = "bearer"
WEBSOCKET_TOKEN_TTL_SECONDS = 30
INVALID_CREDENTIALS_ERROR = "Incorrect username or password"
EXECUTION_NOT_FOUND_ERROR = "Execution not found"


class AuthService:
    """Authenticate users and authorize ephemeral execution tokens."""

    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)

    async def authenticate_user(self, username: str, password: str) -> Token:
        """Return a bearer token when the submitted credentials are valid."""
        logger = get_security_logger(
            username=username, action="authenticate", event_type="login_attempt"
        )
        if not username or not password or len(username) > 100 or len(password) > 200:
            logger.bind(
                event_type="login_failed", failure_reason="invalid_credentials"
            ).warning("Authentication failed")
            raise AuthenticationException(INVALID_CREDENTIALS_ERROR)

        user = self.db.exec(select(User).where(User.username == username)).first()
        if user is None or not security.verify_password(password, user.password_hash):
            logger.bind(event_type="login_failed").warning("Authentication failed")
            raise AuthenticationException(INVALID_CREDENTIALS_ERROR)

        token = security.create_access_token(
            data={"sub": user.username},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        logger.bind(user_id=user.id, role=user.role, event_type="login_success").info(
            "Authentication successful"
        )
        return Token(access_token=token, token_type=TOKEN_TYPE_BEARER)

    async def create_websocket_token(
        self, execution_id: int, current_user: User
    ) -> WebSocketToken:
        """Return a one-use token after resolving its execution and case access."""
        logger = get_security_logger(
            action="create_websocket_token",
            user_id=current_user.id,
            execution_id=execution_id,
            event_type="websocket_token_attempt",
        )
        execution = self.db.get(HuntExecution, execution_id)
        if execution is None:
            logger.bind(
                event_type="websocket_token_failed",
                failure_reason="execution_not_found",
            ).warning("WebSocket token creation failed")
            raise ResourceNotFoundException(EXECUTION_NOT_FOUND_ERROR)

        try:
            self.case_access.readable(current_user, execution.case_id)
        except AuthorizationException:
            logger.bind(
                event_type="websocket_token_failed", failure_reason="access_denied"
            ).warning("WebSocket token creation denied")
            raise
        if current_user.id is None:
            raise AuthenticationException("Could not validate credentials")
        token = security.ephemeral_token_manager.create_token(
            current_user.id, execution_id
        )
        logger.bind(
            event_type="websocket_token_success", case_id=execution.case_id
        ).info("WebSocket token created successfully")
        return WebSocketToken(
            token=token,
            execution_id=execution_id,
            expires_in=WEBSOCKET_TOKEN_TTL_SECONDS,
        )
