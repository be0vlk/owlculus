"""
Tests for AuthService functionality
"""

from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from app.core import security
from app.core.config import settings
from app.database import models
from app.services.auth_service import AuthService
from fastapi import HTTPException, status
from sqlmodel import Session


class TestAuthService:
    """Test cases for AuthService"""

    @pytest.fixture(name="auth_service_instance")
    def auth_service_fixture(self, session: Session):
        """Create an AuthService instance for testing"""
        return AuthService(session)

    def test_init_auth_service(self, session: Session):
        """Test AuthService initialization"""
        service = AuthService(session)
        assert service.db == session

    @pytest.mark.asyncio
    async def test_authenticate_user_success(
        self,
        auth_service_instance: AuthService,
        test_admin: models.User,
    ):
        """Test successful user authentication"""
        username = "testuser"
        password = "testpass123"

        # Mock crud.get_user_by_username to return a user
        with patch(
            "app.services.auth_service.crud.get_user_by_username"
        ) as mock_get_user:
            # Create a mock user with hashed password
            mock_user = Mock()
            mock_user.username = username
            mock_user.password_hash = security.get_password_hash(password)
            mock_get_user.return_value = mock_user

            # Mock security.verify_password to return True
            with patch(
                "app.services.auth_service.security.verify_password"
            ) as mock_verify:
                mock_verify.return_value = True

                # Mock security.create_access_token
                with patch(
                    "app.services.auth_service.security.create_access_token"
                ) as mock_create_token:
                    mock_token = "mock_access_token"
                    mock_create_token.return_value = mock_token

                    result = await auth_service_instance.authenticate_user(
                        username, password
                    )

                    # Verify the result
                    assert result["access_token"] == mock_token
                    assert result["token_type"] == "bearer"

                    # Verify the mocks were called correctly
                    mock_get_user.assert_called_once_with(
                        auth_service_instance.db, username=username
                    )
                    mock_verify.assert_called_once_with(
                        password, mock_user.password_hash
                    )
                    mock_create_token.assert_called_once()

                    # Verify token creation parameters
                    call_args = mock_create_token.call_args
                    assert call_args[1]["data"]["sub"] == username
                    assert isinstance(call_args[1]["expires_delta"], timedelta)
                    assert (
                        call_args[1]["expires_delta"].total_seconds()
                        == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
                    )

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(
        self,
        auth_service_instance: AuthService,
    ):
        """Test authentication with non-existent user"""
        username = "nonexistent"
        password = "password"

        # Mock crud.get_user_by_username to return None
        with patch(
            "app.services.auth_service.crud.get_user_by_username"
        ) as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await auth_service_instance.authenticate_user(username, password)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Incorrect username or password" in exc_info.value.detail
            assert exc_info.value.headers["Authorization"] == "Bearer"

            mock_get_user.assert_called_once_with(
                auth_service_instance.db, username=username
            )

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(
        self,
        auth_service_instance: AuthService,
    ):
        """Test authentication with incorrect password"""
        username = "testuser"
        password = "wrongpassword"
        correct_password = "correctpassword"

        # Mock crud.get_user_by_username to return a user
        with patch(
            "app.services.auth_service.crud.get_user_by_username"
        ) as mock_get_user:
            mock_user = Mock()
            mock_user.username = username
            mock_user.password_hash = security.get_password_hash(correct_password)
            mock_get_user.return_value = mock_user

            # Mock security.verify_password to return False
            with patch(
                "app.services.auth_service.security.verify_password"
            ) as mock_verify:
                mock_verify.return_value = False

                with pytest.raises(HTTPException) as exc_info:
                    await auth_service_instance.authenticate_user(username, password)

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Incorrect username or password" in exc_info.value.detail
                assert exc_info.value.headers["Authorization"] == "Bearer"

                mock_get_user.assert_called_once_with(
                    auth_service_instance.db, username=username
                )
                mock_verify.assert_called_once_with(password, mock_user.password_hash)

    @pytest.mark.asyncio
    async def test_authenticate_user_with_real_password_hashing(
        self,
        auth_service_instance: AuthService,
    ):
        """Test authentication with real password hashing functions"""
        username = "testuser"
        password = "testpass123"

        # Create a real password hash
        password_hash = security.get_password_hash(password)

        # Mock crud.get_user_by_username to return a user with real hash
        with patch(
            "app.services.auth_service.crud.get_user_by_username"
        ) as mock_get_user:
            mock_user = Mock()
            mock_user.username = username
            mock_user.password_hash = password_hash
            mock_get_user.return_value = mock_user

            # Mock security.create_access_token
            with patch(
                "app.services.auth_service.security.create_access_token"
            ) as mock_create_token:
                mock_token = "real_test_token"
                mock_create_token.return_value = mock_token

                # Don't mock verify_password - let it use the real function
                result = await auth_service_instance.authenticate_user(
                    username, password
                )

                assert result["access_token"] == mock_token
                assert result["token_type"] == "bearer"

                mock_get_user.assert_called_once_with(
                    auth_service_instance.db, username=username
                )
                mock_create_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_with_real_password_hashing_wrong_password(
        self,
        auth_service_instance: AuthService,
    ):
        """Test authentication failure with real password hashing"""
        username = "testuser"
        correct_password = "correctpass123"
        wrong_password = "wrongpass123"

        # Create a real password hash for the correct password
        password_hash = security.get_password_hash(correct_password)

        # Mock crud.get_user_by_username to return a user with real hash
        with patch(
            "app.services.auth_service.crud.get_user_by_username"
        ) as mock_get_user:
            mock_user = Mock()
            mock_user.username = username
            mock_user.password_hash = password_hash
            mock_get_user.return_value = mock_user

            # Don't mock verify_password - let it use the real function
            with pytest.raises(HTTPException) as exc_info:
                await auth_service_instance.authenticate_user(username, wrong_password)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Incorrect username or password" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_authenticate_user_token_creation_with_custom_expiry(
        self,
        auth_service_instance: AuthService,
    ):
        """Test that token creation uses settings for expiry time"""
        username = "testuser"
        password = "testpass123"

        # Mock the settings to have a specific expire time
        original_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        test_expire_minutes = 60  # 1 hour

        try:
            settings.ACCESS_TOKEN_EXPIRE_MINUTES = test_expire_minutes

            with patch(
                "app.services.auth_service.crud.get_user_by_username"
            ) as mock_get_user:
                mock_user = Mock()
                mock_user.username = username
                mock_user.password_hash = security.get_password_hash(password)
                mock_get_user.return_value = mock_user

                with patch(
                    "app.services.auth_service.security.verify_password"
                ) as mock_verify:
                    mock_verify.return_value = True

                    with patch(
                        "app.services.auth_service.security.create_access_token"
                    ) as mock_create_token:
                        mock_token = "custom_expiry_token"
                        mock_create_token.return_value = mock_token

                        result = await auth_service_instance.authenticate_user(
                            username, password
                        )

                        assert result["access_token"] == mock_token

                        # Verify the expiry time was set correctly
                        call_args = mock_create_token.call_args
                        expires_delta = call_args[1]["expires_delta"]
                        assert expires_delta.total_seconds() == test_expire_minutes * 60

        finally:
            # Restore original setting
            settings.ACCESS_TOKEN_EXPIRE_MINUTES = original_expire_minutes

    @pytest.mark.asyncio
    async def test_authenticate_user_database_error(
        self,
        auth_service_instance: AuthService,
    ):
        """Test authentication when database operation fails"""
        username = "testuser"
        password = "testpass123"

        # Mock crud.get_user_by_username to raise an exception
        with patch(
            "app.services.auth_service.crud.get_user_by_username"
        ) as mock_get_user:
            mock_get_user.side_effect = Exception("Database connection error")

            with pytest.raises(Exception) as exc_info:
                await auth_service_instance.authenticate_user(username, password)

            assert "Database connection error" in str(exc_info.value)
            mock_get_user.assert_called_once_with(
                auth_service_instance.db, username=username
            )

    @pytest.mark.asyncio
    async def test_authenticate_user_empty_credentials(
        self,
        auth_service_instance: AuthService,
    ):
        """Test authentication with empty credentials"""
        # Test empty username
        with patch(
            "app.services.auth_service.crud.get_user_by_username"
        ) as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await auth_service_instance.authenticate_user("", "password")

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

        # Test empty password
        with patch(
            "app.services.auth_service.crud.get_user_by_username"
        ) as mock_get_user:
            mock_user = Mock()
            mock_user.username = "testuser"
            mock_user.password_hash = security.get_password_hash("realpassword")
            mock_get_user.return_value = mock_user

            with patch(
                "app.services.auth_service.security.verify_password"
            ) as mock_verify:
                mock_verify.return_value = False

                with pytest.raises(HTTPException) as exc_info:
                    await auth_service_instance.authenticate_user("testuser", "")

                assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_authenticate_user_token_creation_error(
        self,
        auth_service_instance: AuthService,
    ):
        """Test authentication when token creation fails"""
        username = "testuser"
        password = "testpass123"

        with patch(
            "app.services.auth_service.crud.get_user_by_username"
        ) as mock_get_user:
            mock_user = Mock()
            mock_user.username = username
            mock_user.password_hash = security.get_password_hash(password)
            mock_get_user.return_value = mock_user

            with patch(
                "app.services.auth_service.security.verify_password"
            ) as mock_verify:
                mock_verify.return_value = True

                with patch(
                    "app.services.auth_service.security.create_access_token"
                ) as mock_create_token:
                    mock_create_token.side_effect = Exception("Token creation failed")

                    with pytest.raises(Exception) as exc_info:
                        await auth_service_instance.authenticate_user(
                            username, password
                        )

                    assert "Token creation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authenticate_user_integration_with_real_user(
        self,
        auth_service_instance: AuthService,
        test_admin: models.User,
    ):
        """Test authentication using a real user from test fixtures"""
        username = test_admin.username
        # We need to know the original password since test_admin has hashed password
        password = "admin_password"  # This should match what's used in conftest.py

        # Mock crud to return our test user
        with patch(
            "app.services.auth_service.crud.get_user_by_username"
        ) as mock_get_user:
            mock_get_user.return_value = test_admin

            # Mock verify_password to return True for this test
            with patch(
                "app.services.auth_service.security.verify_password"
            ) as mock_verify:
                mock_verify.return_value = True

                with patch(
                    "app.services.auth_service.security.create_access_token"
                ) as mock_create_token:
                    mock_token = "integration_test_token"
                    mock_create_token.return_value = mock_token

                    result = await auth_service_instance.authenticate_user(
                        username, password
                    )

                    assert result["access_token"] == mock_token
                    assert result["token_type"] == "bearer"

                    # Verify the token was created with the correct username
                    call_args = mock_create_token.call_args
                    assert call_args[1]["data"]["sub"] == username
