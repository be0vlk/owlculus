"""Session-backed authentication and WebSocket-token operations."""

from datetime import timedelta

from anyio import CapacityLimiter, to_thread
from sqlmodel import Session, select

from app.core import security
from app.core.config import settings
from app.core.database_boundary import on_transport_loop
from app.core.exceptions import (
    AuthenticationException,
)
from app.core.logging import get_security_logger
from app.database.models import User
from app.schemas.auth_schema import Token, WebSocketToken
from app.services.case_access import CaseAccess

TOKEN_TYPE_BEARER = "bearer"
WEBSOCKET_TOKEN_TTL_SECONDS = 30
INVALID_CREDENTIALS_ERROR = "Incorrect username or password"
BCRYPT_MAX_PASSWORD_BYTES = 72
# Keep login CPU work bounded without consuming the default limiter used by
# synchronous API endpoints and dependencies. Shared abuse limits are separate.
LOGIN_PASSWORD_WORKERS = 4
_password_verification_limiter = CapacityLimiter(LOGIN_PASSWORD_WORKERS)
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
        if (
            not username
            or not password
            or len(username) > 100
            or len(password) > 200
            or len(password.encode("utf-8")) > BCRYPT_MAX_PASSWORD_BYTES
        ):
            logger.bind(
                event_type="login_failed", failure_reason="invalid_credentials"
            ).warning("Authentication failed")
            raise AuthenticationException(INVALID_CREDENTIALS_ERROR)

        user = self.db.exec(select(User).where(User.username == username)).first()
        # Capture the version from the same row read as the password hash. A reset
        # racing password verification can only make this token stale, never fresh.
        identity = user.auth_identity if user else None
        version = user.session_version if user else None
        if (
            user is None
            or not user.is_active
            or not await self._verify_password(password, user.password_hash)
        ):
            logger.bind(event_type="login_failed").warning("Authentication failed")
            raise AuthenticationException(INVALID_CREDENTIALS_ERROR)

        token = security.create_access_token(
            data={"sub": identity, "session_version": version},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        logger.bind(user_id=user.id, role=user.role, event_type="login_success").info(
            "Authentication successful"
        )
        return Token(access_token=token, token_type=TOKEN_TYPE_BEARER)

    @staticmethod
    async def _verify_password(password: str, password_hash: str) -> bool:
        return await on_transport_loop(
            lambda: to_thread.run_sync(
                security.verify_password,
                password,
                password_hash,
                limiter=_password_verification_limiter,
            )
        )

    async def create_websocket_token(
        self, execution_id: int, current_user: User, kind: str = "hunt"
    ) -> WebSocketToken:
        """Return a one-use token after resolving its execution and case access."""
        logger = get_security_logger(
            action="create_websocket_token",
            user_id=current_user.id,
            execution_id=execution_id,
            event_type="websocket_token_attempt",
        )
        import asyncio

        from fastapi import HTTPException

        from app.executions.observation import readable_execution

        identity, version = current_user.auth_identity, current_user.session_version
        execution = readable_execution(self.db, current_user.id, kind, execution_id)
        if current_user.id is None:
            raise AuthenticationException("Could not validate credentials")
        try:
            token = await asyncio.to_thread(
                security.ephemeral_token_manager.create_token,
                current_user.id,
                execution_id,
                kind,
                identity,
                version,
            )
        except Exception:  # noqa: BLE001 - never expose Redis credentials
            raise HTTPException(
                503,
                "Live updates are unavailable; retained investigation results remain available",
            ) from None
        logger.bind(
            event_type="websocket_token_success", case_id=execution.case_id
        ).info("WebSocket token created successfully")
        return WebSocketToken(
            token=token,
            execution_id=execution_id,
            expires_in=WEBSOCKET_TOKEN_TTL_SECONDS,
        )
