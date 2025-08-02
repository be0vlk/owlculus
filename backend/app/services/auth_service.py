"""
Authentication service handling all auth-related business logic
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, Optional, Protocol

from sqlmodel import Session

from app.core import security
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    BaseException,
    ResourceNotFoundException,
)
from app.core.logging import get_security_logger
from app.database import crud
from app.database.models import HuntExecution, User


# Constants
DEFAULT_TOKEN_EXPIRY_MINUTES = 30
TOKEN_TYPE_BEARER = "bearer"
WEBSOCKET_TOKEN_TTL_SECONDS = 30

# Error messages (kept generic for security)
INVALID_CREDENTIALS_ERROR = "Incorrect username or password"
EXECUTION_NOT_FOUND_ERROR = "Execution not found"
ACCESS_DENIED_ERROR = "Access denied"
AUTH_SERVICE_ERROR = "Authentication service error"
WEBSOCKET_TOKEN_ERROR = "WebSocket token service error"


@dataclass
class AuthToken:
    """Authentication token response"""
    access_token: str
    token_type: str = TOKEN_TYPE_BEARER


@dataclass
class WebSocketToken:
    """WebSocket authentication token response"""
    token: str
    execution_id: int
    expires_in: int


class UserRepository(Protocol):
    """Protocol for user data access"""
    async def get_by_username(self, username: str) -> Optional[User]:
        ...


class ExecutionRepository(Protocol):
    """Protocol for execution data access"""
    def get_by_id(self, execution_id: int) -> Optional[HuntExecution]:
        ...


class CaseAccessChecker(Protocol):
    """Protocol for case access validation"""
    def has_access(self, case_id: int, user: User) -> bool:
        ...


class PasswordHasher(ABC):
    """Abstract base class for password hashing"""
    @abstractmethod
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        ...


class TokenGenerator(ABC):
    """Abstract base class for token generation"""
    @abstractmethod
    def create_access_token(self, username: str, expires_delta: timedelta) -> str:
        ...
    
    @abstractmethod
    def create_ephemeral_token(self, user_id: int, execution_id: int) -> str:
        ...


class BcryptPasswordHasher(PasswordHasher):
    """Bcrypt implementation of password hasher"""
    def verify(self, plain_password: str, hashed_password: str) -> bool:
        return security.verify_password(plain_password, hashed_password)


class JWTTokenGenerator(TokenGenerator):
    """JWT implementation of token generator"""
    def create_access_token(self, username: str, expires_delta: timedelta) -> str:
        return security.create_access_token(
            data={"sub": username},
            expires_delta=expires_delta
        )
    
    def create_ephemeral_token(self, user_id: int, execution_id: int) -> str:
        return security.ephemeral_token_manager.create_token(user_id, execution_id)


class DatabaseUserRepository(UserRepository):
    """Database implementation of user repository"""
    def __init__(self, db: Session):
        self.db = db
    
    async def get_by_username(self, username: str) -> Optional[User]:
        return await crud.get_user_by_username(self.db, username=username)


class DatabaseExecutionRepository(ExecutionRepository):
    """Database implementation of execution repository"""
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, execution_id: int) -> Optional[HuntExecution]:
        return self.db.get(HuntExecution, execution_id)


class DatabaseCaseAccessChecker(CaseAccessChecker):
    """Database implementation of case access checker"""
    def __init__(self, db: Session):
        self.db = db
    
    def has_access(self, case_id: int, user: User) -> bool:
        from app.core.dependencies import check_case_access
        try:
            check_case_access(self.db, case_id, user)
            return True
        except Exception:
            return False


class AuthenticationService:
    """Service for user authentication"""
    
    def __init__(
        self,
        user_repository: UserRepository,
        password_hasher: PasswordHasher,
        token_generator: TokenGenerator,
    ):
        self.user_repository = user_repository
        self.password_hasher = password_hasher
        self.token_generator = token_generator
    
    async def authenticate(self, username: str, password: str) -> AuthToken:
        """Authenticate user and return access token"""
        self._validate_credentials(username, password)
        
        logger = self._get_auth_logger(username, "authenticate", "login_attempt")
        logger.info("Authentication attempt started")
        
        try:
            user = await self._verify_user_credentials(username, password, logger)
            token = self._generate_access_token(user.username)
            
            self._log_successful_auth(logger, user)
            return AuthToken(access_token=token, token_type=TOKEN_TYPE_BEARER)
            
        except AuthenticationException:
            raise
        except Exception as e:
            self._log_auth_error(logger, str(e))
            raise BaseException(AUTH_SERVICE_ERROR)
    
    def _validate_credentials(self, username: str, password: str) -> None:
        """Validate input credentials format"""
        if not username or not password:
            raise AuthenticationException(INVALID_CREDENTIALS_ERROR)
        
        if len(username) > 100 or len(password) > 200:
            raise AuthenticationException(INVALID_CREDENTIALS_ERROR)
    
    async def _verify_user_credentials(
        self,
        username: str,
        password: str,
        logger
    ) -> User:
        """Verify user exists and password matches"""
        user = await self.user_repository.get_by_username(username)
        
        if not user:
            self._log_failed_auth(logger, "user_not_found")
            raise AuthenticationException(INVALID_CREDENTIALS_ERROR)
        
        if not self.password_hasher.verify(password, user.password_hash):
            self._log_failed_auth(logger, "invalid_password", user.id)
            raise AuthenticationException(INVALID_CREDENTIALS_ERROR)
        
        return user
    
    def _generate_access_token(self, username: str) -> str:
        """Generate JWT access token"""
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return self.token_generator.create_access_token(username, expires_delta)
    
    def _get_auth_logger(self, username: str, action: str, event_type: str):
        """Get configured security logger"""
        return get_security_logger(
            username=username,
            action=action,
            event_type=event_type
        )
    
    def _log_successful_auth(self, logger, user: User) -> None:
        """Log successful authentication"""
        logger.bind(
            user_id=user.id,
            role=user.role,
            event_type="login_success"
        ).info("Authentication successful")
    
    def _log_failed_auth(
        self,
        logger,
        reason: str,
        user_id: Optional[int] = None
    ) -> None:
        """Log failed authentication attempt"""
        log_data = {
            "event_type": "login_failed",
            "failure_reason": reason
        }
        if user_id:
            log_data["user_id"] = user_id
        
        logger.bind(**log_data).warning("Authentication failed")
    
    def _log_auth_error(self, logger, error: str) -> None:
        """Log authentication system error"""
        logger.error(
            f"Authentication error: {error}",
            event_type="login_error",
            error_type="system_error"
        )


class WebSocketTokenService:
    """Service for WebSocket token management"""
    
    def __init__(
        self,
        execution_repository: ExecutionRepository,
        case_access_checker: CaseAccessChecker,
        token_generator: TokenGenerator,
    ):
        self.execution_repository = execution_repository
        self.case_access_checker = case_access_checker
        self.token_generator = token_generator
    
    async def create_token(
        self,
        execution_id: int,
        current_user: User
    ) -> WebSocketToken:
        """Create single-use ephemeral token for WebSocket authentication"""
        logger = self._get_ws_logger(current_user, execution_id)
        
        try:
            execution = self._get_and_validate_execution(execution_id, logger)
            self._validate_case_access(execution, current_user, logger)
            
            token = self._create_ephemeral_token(current_user.id, execution_id)
            
            self._log_token_created(logger, execution.case_id)
            
            return WebSocketToken(
                token=token,
                execution_id=execution_id,
                expires_in=WEBSOCKET_TOKEN_TTL_SECONDS
            )
            
        except (ResourceNotFoundException, AuthorizationException):
            raise
        except Exception as e:
            self._log_token_error(logger, str(e))
            raise BaseException(WEBSOCKET_TOKEN_ERROR)
    
    def _get_and_validate_execution(
        self,
        execution_id: int,
        logger
    ) -> HuntExecution:
        """Get execution and validate it exists"""
        execution = self.execution_repository.get_by_id(execution_id)
        
        if not execution:
            self._log_token_failed(logger, "execution_not_found")
            raise ResourceNotFoundException(EXECUTION_NOT_FOUND_ERROR)
        
        return execution
    
    def _validate_case_access(
        self,
        execution: HuntExecution,
        user: User,
        logger
    ) -> None:
        """Validate user has access to the case"""
        if not self.case_access_checker.has_access(execution.case_id, user):
            self._log_token_failed(
                logger,
                "access_denied",
                case_id=execution.case_id
            )
            raise AuthorizationException(ACCESS_DENIED_ERROR)
    
    def _create_ephemeral_token(self, user_id: int, execution_id: int) -> str:
        """Create the ephemeral token"""
        return self.token_generator.create_ephemeral_token(user_id, execution_id)
    
    def _get_ws_logger(self, user: User, execution_id: int):
        """Get configured WebSocket logger"""
        return get_security_logger(
            user_id=user.id,
            username=user.username,
            action="create_websocket_token",
            execution_id=execution_id,
        )
    
    def _log_token_created(self, logger, case_id: int) -> None:
        """Log successful token creation"""
        logger.info(
            "WebSocket token created successfully",
            event_type="ws_token_created",
            case_id=case_id,
        )
    
    def _log_token_failed(self, logger, reason: str, **kwargs) -> None:
        """Log failed token creation"""
        log_data = {
            "event_type": "ws_token_failed",
            "failure_reason": reason,
            **kwargs
        }
        logger.warning("WebSocket token creation failed", **log_data)
    
    def _log_token_error(self, logger, error: str) -> None:
        """Log token creation system error"""
        logger.error(
            f"WebSocket token creation error: {error}",
            event_type="ws_token_error",
            error_type="system_error"
        )


class AuthService:
    """
    Facade for authentication services maintaining backward compatibility
    """
    
    def __init__(self, db: Session):
        self.db = db
        
        # Initialize repositories
        user_repo = DatabaseUserRepository(db)
        exec_repo = DatabaseExecutionRepository(db)
        access_checker = DatabaseCaseAccessChecker(db)
        
        # Initialize utilities
        password_hasher = BcryptPasswordHasher()
        token_generator = JWTTokenGenerator()
        
        # Initialize services
        self.auth_service = AuthenticationService(
            user_repository=user_repo,
            password_hasher=password_hasher,
            token_generator=token_generator
        )
        
        self.ws_token_service = WebSocketTokenService(
            execution_repository=exec_repo,
            case_access_checker=access_checker,
            token_generator=token_generator
        )
    
    async def authenticate_user(self, username: str, password: str) -> dict:
        """Authenticate a user and return an access token"""
        result = await self.auth_service.authenticate(username, password)
        return {"access_token": result.access_token, "token_type": result.token_type}
    
    async def create_websocket_token(
        self,
        execution_id: int,
        current_user: User
    ) -> dict:
        """Create a single-use ephemeral token for WebSocket authentication"""
        result = await self.ws_token_service.create_token(execution_id, current_user)
        return {
            "token": result.token,
            "execution_id": result.execution_id,
            "expires_in": result.expires_in,
        }