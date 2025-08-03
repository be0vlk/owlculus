"""
Comprehensive test suite for refactored authentication service
"""

import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    BaseException,
    ResourceNotFoundException,
)
from app.database.models import HuntExecution, User
from app.services.auth_service import (
    AUTH_SERVICE_ERROR,
    ACCESS_DENIED_ERROR,
    AuthService,
    AuthenticationService,
    AuthToken,
    BcryptPasswordHasher,
    DatabaseCaseAccessChecker,
    DatabaseExecutionRepository,
    DatabaseUserRepository,
    EXECUTION_NOT_FOUND_ERROR,
    INVALID_CREDENTIALS_ERROR,
    JWTTokenGenerator,
    TOKEN_TYPE_BEARER,
    WEBSOCKET_TOKEN_ERROR,
    WEBSOCKET_TOKEN_TTL_SECONDS,
    WebSocketToken,
    WebSocketTokenService,
)


class TestAuthenticationService:
    """Test suite for AuthenticationService"""
    
    @pytest.fixture
    def mock_user_repository(self):
        repo = Mock()
        repo.get_by_username = AsyncMock()
        return repo
    
    @pytest.fixture
    def mock_password_hasher(self):
        hasher = Mock()
        hasher.verify = Mock()
        return hasher
    
    @pytest.fixture
    def mock_token_generator(self):
        generator = Mock()
        generator.create_access_token = Mock(return_value="test_token")
        generator.create_ephemeral_token = Mock(return_value="ephemeral_token")
        return generator
    
    @pytest.fixture
    def auth_service(self, mock_user_repository, mock_password_hasher, mock_token_generator):
        return AuthenticationService(
            user_repository=mock_user_repository,
            password_hasher=mock_password_hasher,
            token_generator=mock_token_generator
        )
    
    @pytest.fixture
    def test_user(self):
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.password_hash = "hashed_password"
        user.role = "Investigator"
        return user
    
    @pytest.mark.asyncio
    async def test_authenticate_success(
        self,
        auth_service,
        mock_user_repository,
        mock_password_hasher,
        mock_token_generator,
        test_user
    ):
        """Test successful authentication"""
        mock_user_repository.get_by_username.return_value = test_user
        mock_password_hasher.verify.return_value = True
        
        with patch('app.services.auth_service.get_security_logger') as mock_logger:
            result = await auth_service.authenticate("testuser", "password123")
        
        assert isinstance(result, AuthToken)
        assert result.access_token == "test_token"
        assert result.token_type == TOKEN_TYPE_BEARER
        
        mock_user_repository.get_by_username.assert_called_once_with("testuser")
        mock_password_hasher.verify.assert_called_once_with("password123", "hashed_password")
    
    @pytest.mark.asyncio
    async def test_authenticate_empty_credentials(self, auth_service):
        """Test authentication with empty credentials"""
        with pytest.raises(AuthenticationException) as exc_info:
            await auth_service.authenticate("", "password")
        assert str(exc_info.value) == INVALID_CREDENTIALS_ERROR
        
        with pytest.raises(AuthenticationException) as exc_info:
            await auth_service.authenticate("user", "")
        assert str(exc_info.value) == INVALID_CREDENTIALS_ERROR
    
    @pytest.mark.asyncio
    async def test_authenticate_long_credentials(self, auth_service):
        """Test authentication with overly long credentials"""
        with pytest.raises(AuthenticationException) as exc_info:
            await auth_service.authenticate("a" * 101, "password")
        assert str(exc_info.value) == INVALID_CREDENTIALS_ERROR
        
        with pytest.raises(AuthenticationException) as exc_info:
            await auth_service.authenticate("user", "a" * 201)
        assert str(exc_info.value) == INVALID_CREDENTIALS_ERROR
    
    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(
        self,
        auth_service,
        mock_user_repository
    ):
        """Test authentication when user doesn't exist"""
        mock_user_repository.get_by_username.return_value = None
        
        with patch('app.services.auth_service.get_security_logger') as mock_logger:
            with pytest.raises(AuthenticationException) as exc_info:
                await auth_service.authenticate("nonexistent", "password")
        
        assert str(exc_info.value) == INVALID_CREDENTIALS_ERROR
    
    @pytest.mark.asyncio
    async def test_authenticate_invalid_password(
        self,
        auth_service,
        mock_user_repository,
        mock_password_hasher,
        test_user
    ):
        """Test authentication with invalid password"""
        mock_user_repository.get_by_username.return_value = test_user
        mock_password_hasher.verify.return_value = False
        
        with patch('app.services.auth_service.get_security_logger') as mock_logger:
            with pytest.raises(AuthenticationException) as exc_info:
                await auth_service.authenticate("testuser", "wrongpassword")
        
        assert str(exc_info.value) == INVALID_CREDENTIALS_ERROR
    
    @pytest.mark.asyncio
    async def test_authenticate_system_error(
        self,
        auth_service,
        mock_user_repository
    ):
        """Test authentication system error handling"""
        mock_user_repository.get_by_username.side_effect = Exception("Database error")
        
        with patch('app.services.auth_service.get_security_logger') as mock_logger:
            with pytest.raises(BaseException) as exc_info:
                await auth_service.authenticate("testuser", "password")
        
        assert str(exc_info.value) == AUTH_SERVICE_ERROR


class TestWebSocketTokenService:
    """Test suite for WebSocketTokenService"""
    
    @pytest.fixture
    def mock_execution_repository(self):
        repo = Mock()
        repo.get_by_id = Mock()
        return repo
    
    @pytest.fixture
    def mock_case_access_checker(self):
        checker = Mock()
        checker.has_access = Mock()
        return checker
    
    @pytest.fixture
    def mock_token_generator(self):
        generator = Mock()
        generator.create_ephemeral_token = Mock(return_value="ws_token")
        return generator
    
    @pytest.fixture
    def ws_token_service(
        self,
        mock_execution_repository,
        mock_case_access_checker,
        mock_token_generator
    ):
        return WebSocketTokenService(
            execution_repository=mock_execution_repository,
            case_access_checker=mock_case_access_checker,
            token_generator=mock_token_generator
        )
    
    @pytest.fixture
    def test_user(self):
        user = Mock(spec=User)
        user.id = 1
        user.username = "testuser"
        user.role = "Investigator"
        return user
    
    @pytest.fixture
    def test_execution(self):
        execution = Mock(spec=HuntExecution)
        execution.id = 100
        execution.case_id = 10
        return execution
    
    @pytest.mark.asyncio
    async def test_create_token_success(
        self,
        ws_token_service,
        mock_execution_repository,
        mock_case_access_checker,
        mock_token_generator,
        test_user,
        test_execution
    ):
        """Test successful WebSocket token creation"""
        mock_execution_repository.get_by_id.return_value = test_execution
        mock_case_access_checker.has_access.return_value = True
        
        with patch('app.services.auth_service.get_security_logger') as mock_logger:
            result = await ws_token_service.create_token(100, test_user)
        
        assert isinstance(result, WebSocketToken)
        assert result.token == "ws_token"
        assert result.execution_id == 100
        assert result.expires_in == WEBSOCKET_TOKEN_TTL_SECONDS
        
        mock_execution_repository.get_by_id.assert_called_once_with(100)
        mock_case_access_checker.has_access.assert_called_once_with(10, test_user)
        mock_token_generator.create_ephemeral_token.assert_called_once_with(1, 100)
    
    @pytest.mark.asyncio
    async def test_create_token_execution_not_found(
        self,
        ws_token_service,
        mock_execution_repository,
        test_user
    ):
        """Test token creation with non-existent execution"""
        mock_execution_repository.get_by_id.return_value = None
        
        with patch('app.services.auth_service.get_security_logger') as mock_logger:
            with pytest.raises(ResourceNotFoundException) as exc_info:
                await ws_token_service.create_token(999, test_user)
        
        assert str(exc_info.value) == EXECUTION_NOT_FOUND_ERROR
    
    @pytest.mark.asyncio
    async def test_create_token_access_denied(
        self,
        ws_token_service,
        mock_execution_repository,
        mock_case_access_checker,
        test_user,
        test_execution
    ):
        """Test token creation with access denied"""
        mock_execution_repository.get_by_id.return_value = test_execution
        mock_case_access_checker.has_access.return_value = False
        
        with patch('app.services.auth_service.get_security_logger') as mock_logger:
            with pytest.raises(AuthorizationException) as exc_info:
                await ws_token_service.create_token(100, test_user)
        
        assert str(exc_info.value) == ACCESS_DENIED_ERROR
    
    @pytest.mark.asyncio
    async def test_create_token_system_error(
        self,
        ws_token_service,
        mock_execution_repository,
        test_user
    ):
        """Test token creation system error handling"""
        mock_execution_repository.get_by_id.side_effect = Exception("Database error")
        
        with patch('app.services.auth_service.get_security_logger') as mock_logger:
            with pytest.raises(BaseException) as exc_info:
                await ws_token_service.create_token(100, test_user)
        
        assert str(exc_info.value) == WEBSOCKET_TOKEN_ERROR


class TestAuthServiceFacade:
    """Test suite for AuthService facade"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.fixture
    def auth_service(self, mock_db):
        return AuthService(mock_db)
    
    @pytest.mark.asyncio
    async def test_authenticate_user_facade(self, auth_service):
        """Test authenticate_user facade method"""
        mock_auth_result = AuthToken(access_token="test_token", token_type="bearer")
        
        with patch.object(
            auth_service.auth_service,
            'authenticate',
            new_callable=AsyncMock,
            return_value=mock_auth_result
        ) as mock_authenticate:
            result = await auth_service.authenticate_user("user", "pass")
        
        assert result == {"access_token": "test_token", "token_type": "bearer"}
        mock_authenticate.assert_called_once_with("user", "pass")
    
    @pytest.mark.asyncio
    async def test_create_websocket_token_facade(self, auth_service):
        """Test create_websocket_token facade method"""
        mock_user = Mock(spec=User)
        mock_ws_result = WebSocketToken(
            token="ws_token",
            execution_id=100,
            expires_in=30
        )
        
        with patch.object(
            auth_service.ws_token_service,
            'create_token',
            new_callable=AsyncMock,
            return_value=mock_ws_result
        ) as mock_create_token:
            result = await auth_service.create_websocket_token(100, mock_user)
        
        assert result == {
            "token": "ws_token",
            "execution_id": 100,
            "expires_in": 30
        }
        mock_create_token.assert_called_once_with(100, mock_user)


class TestDatabaseImplementations:
    """Test suite for database implementation classes"""
    
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.mark.asyncio
    async def test_database_user_repository(self, mock_db):
        """Test DatabaseUserRepository"""
        repo = DatabaseUserRepository(mock_db)
        
        with patch('app.services.auth_service.crud.get_user_by_username', new_callable=AsyncMock) as mock_crud:
            mock_crud.return_value = "test_user"
            result = await repo.get_by_username("testuser")
        
        assert result == "test_user"
        mock_crud.assert_called_once_with(mock_db, username="testuser")
    
    def test_database_execution_repository(self, mock_db):
        """Test DatabaseExecutionRepository"""
        repo = DatabaseExecutionRepository(mock_db)
        mock_db.get.return_value = "test_execution"
        
        result = repo.get_by_id(100)
        
        assert result == "test_execution"
        mock_db.get.assert_called_once_with(HuntExecution, 100)
    
    def test_database_case_access_checker_has_access(self, mock_db):
        """Test DatabaseCaseAccessChecker with access"""
        checker = DatabaseCaseAccessChecker(mock_db)
        mock_user = Mock()
        
        with patch('app.core.dependencies.check_case_access') as mock_check:
            result = checker.has_access(10, mock_user)
        
        assert result is True
        mock_check.assert_called_once_with(mock_db, 10, mock_user)
    
    def test_database_case_access_checker_no_access(self, mock_db):
        """Test DatabaseCaseAccessChecker without access"""
        checker = DatabaseCaseAccessChecker(mock_db)
        mock_user = Mock()
        
        with patch('app.core.dependencies.check_case_access') as mock_check:
            mock_check.side_effect = Exception("Access denied")
            result = checker.has_access(10, mock_user)
        
        assert result is False


class TestUtilityClasses:
    """Test suite for utility classes"""
    
    def test_bcrypt_password_hasher(self):
        """Test BcryptPasswordHasher"""
        hasher = BcryptPasswordHasher()
        
        with patch('app.services.auth_service.security.verify_password') as mock_verify:
            mock_verify.return_value = True
            result = hasher.verify("plain", "hashed")
        
        assert result is True
        mock_verify.assert_called_once_with("plain", "hashed")
    
    def test_jwt_token_generator_access_token(self):
        """Test JWTTokenGenerator access token creation"""
        generator = JWTTokenGenerator()
        expires = timedelta(minutes=30)
        
        with patch('app.services.auth_service.security.create_access_token') as mock_create:
            mock_create.return_value = "jwt_token"
            result = generator.create_access_token("user", expires)
        
        assert result == "jwt_token"
        mock_create.assert_called_once_with(
            data={"sub": "user"},
            expires_delta=expires
        )
    
    def test_jwt_token_generator_ephemeral_token(self):
        """Test JWTTokenGenerator ephemeral token creation"""
        generator = JWTTokenGenerator()
        
        with patch('app.services.auth_service.security.ephemeral_token_manager.create_token') as mock_create:
            mock_create.return_value = "ephemeral_token"
            result = generator.create_ephemeral_token(1, 100)
        
        assert result == "ephemeral_token"
        mock_create.assert_called_once_with(1, 100)