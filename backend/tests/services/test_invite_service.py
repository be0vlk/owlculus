"""
Test suite for invitation service business logic.

This module tests invite workflows, validation, expiration handling,
user registration through invites, security logging, and error handling
within the invitation service layer.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app import schemas
from app.core.exceptions import (
    BaseException,
    DuplicateResourceException,
    ResourceNotFoundException,
)
from app.database import models
from app.services.invite_service import (
    INVITE_EXPIRATION_HOURS,
    TOKEN_LENGTH,
    InvalidInviteException,
    InviteException,
    InviteRegistrationException,
    InviteService,
    InviteValidator,
    InviteValidationResult,
    SecurityLogger,
    UserValidator,
)
from sqlmodel import Session


# Fixtures
@pytest.fixture
def mock_db():
    """Create a mock database session"""
    return Mock(spec=Session)


@pytest.fixture
def mock_invite_repo():
    """Create a mock invite repository"""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_user_repo():
    """Create a mock user repository"""
    repo = AsyncMock()
    return repo


@pytest.fixture
def current_user():
    """Create a test user"""
    return models.User(
        id=1,
        username="admin",
        email="admin@test.com",
        role="admin",
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def valid_invite():
    """Create a valid test invite"""
    return models.Invite(
        id=1,
        token="test-token-12345",
        role="investigator",
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=48),
        used_at=None,
        created_by_id=1,
    )


@pytest.fixture
def expired_invite():
    """Create an expired test invite"""
    return models.Invite(
        id=2,
        token="expired-token-12345",
        role="analyst",
        created_at=datetime.utcnow() - timedelta(hours=72),
        expires_at=datetime.utcnow() - timedelta(hours=24),
        used_at=None,
        created_by_id=1,
    )


@pytest.fixture
def used_invite():
    """Create a used test invite"""
    return models.Invite(
        id=3,
        token="used-token-12345",
        role="admin",
        created_at=datetime.utcnow() - timedelta(hours=24),
        expires_at=datetime.utcnow() + timedelta(hours=24),
        used_at=datetime.utcnow() - timedelta(hours=12),
        created_by_id=1,
    )


@pytest.fixture
def invite_service(mock_db, mock_invite_repo, mock_user_repo):
    """Create an invite service with mocked dependencies"""
    return InviteService(mock_db, mock_invite_repo, mock_user_repo)


# Unit Tests for InviteValidator
class TestInviteValidator:
    def test_validate_token_with_valid_invite(self, valid_invite):
        validator = InviteValidator()
        result = validator.validate_token(valid_invite)

        assert result.valid is True
        assert result.role == "investigator"
        assert result.expires_at == valid_invite.expires_at
        assert result.error is None

    def test_validate_token_with_none_invite(self):
        validator = InviteValidator()
        result = validator.validate_token(None)

        assert result.valid is False
        assert result.error == "Invalid invite token"
        assert result.role is None

    def test_validate_token_with_used_invite(self, used_invite):
        validator = InviteValidator()
        result = validator.validate_token(used_invite)

        assert result.valid is False
        assert result.error == "Invite has already been used"

    def test_validate_token_with_expired_invite(self, expired_invite):
        validator = InviteValidator()
        result = validator.validate_token(expired_invite)

        assert result.valid is False
        assert result.error == "Invite has expired"


# Unit Tests for UserValidator
class TestUserValidator:
    @pytest.mark.asyncio
    async def test_validate_registration_success(self, mock_user_repo, mock_db):
        mock_user_repo.get_user_by_username.return_value = None
        mock_user_repo.get_user_by_email.return_value = None

        validator = UserValidator(mock_user_repo)
        error = await validator.validate_registration(
            mock_db, "newuser", "new@test.com"
        )

        assert error is None
        mock_user_repo.get_user_by_username.assert_called_once_with(mock_db, "newuser")
        mock_user_repo.get_user_by_email.assert_called_once_with(
            mock_db, "new@test.com"
        )

    @pytest.mark.asyncio
    async def test_validate_registration_username_taken(self, mock_user_repo, mock_db):
        mock_user_repo.get_user_by_username.return_value = Mock()  # User exists

        validator = UserValidator(mock_user_repo)
        error = await validator.validate_registration(
            mock_db, "existinguser", "new@test.com"
        )

        assert error == "Username already taken"

    @pytest.mark.asyncio
    async def test_validate_registration_email_taken(self, mock_user_repo, mock_db):
        mock_user_repo.get_user_by_username.return_value = None
        mock_user_repo.get_user_by_email.return_value = Mock()  # User exists

        validator = UserValidator(mock_user_repo)
        error = await validator.validate_registration(
            mock_db, "newuser", "existing@test.com"
        )

        assert error == "Email already registered"


# Unit Tests for SecurityLogger
class TestSecurityLogger:
    @patch("app.services.invite_service.get_security_logger")
    def test_log_success(self, mock_get_logger):
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        logger = SecurityLogger({"action": "test"})
        logger.log_success("test_event", "Test message", extra_field="value")

        mock_logger.bind.assert_called_once_with(
            event_type="test_event", extra_field="value"
        )
        mock_logger.bind().info.assert_called_once_with("Test message")

    @patch("app.services.invite_service.get_security_logger")
    def test_log_failure(self, mock_get_logger):
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        logger = SecurityLogger({"action": "test"})
        logger.log_failure("test_event", "Test failure", "invalid_input")

        mock_logger.bind.assert_called_once_with(
            event_type="test_event", failure_reason="invalid_input"
        )
        mock_logger.bind().warning.assert_called_once_with("Test failure")

    @patch("app.services.invite_service.get_security_logger")
    def test_log_error(self, mock_get_logger):
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        logger = SecurityLogger({"action": "test"})
        test_error = Exception("Test error")
        logger.log_error("test_event", "Test error message", test_error)

        mock_logger.bind.assert_called_once_with(
            event_type="test_event", error_type="system_error"
        )
        mock_logger.bind().error.assert_called_once_with(
            "Test error message: Test error"
        )


# Integration Tests for InviteService
class TestInviteService:
    @pytest.mark.asyncio
    async def test_create_invite_success(
        self, invite_service, mock_invite_repo, current_user
    ):
        # Arrange
        invite_create = schemas.InviteCreate(role="Investigator")
        expected_invite = models.Invite(
            id=1,
            token="generated-token",
            role="Investigator",
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=48),
            created_by_id=current_user.id,
        )
        mock_invite_repo.create_invite.return_value = expected_invite

        # Act
        with patch("app.services.invite_service.secrets.token_urlsafe") as mock_token:
            mock_token.return_value = "generated-token"
            result = await invite_service.create_invite(
                invite_create, current_user=current_user
            )

        # Assert
        assert result == expected_invite
        mock_token.assert_called_once_with(TOKEN_LENGTH)
        mock_invite_repo.create_invite.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_invite_database_error(
        self, invite_service, mock_invite_repo, current_user
    ):
        # Arrange
        invite_create = schemas.InviteCreate(role="Admin")
        mock_invite_repo.create_invite.side_effect = Exception("Database error")

        # Act & Assert
        with pytest.raises(InviteException) as exc_info:
            await invite_service.create_invite(invite_create, current_user=current_user)

        assert str(exc_info.value) == "Database error"

    @pytest.mark.asyncio
    async def test_get_invites(
        self,
        invite_service,
        mock_invite_repo,
        current_user,
        valid_invite,
        expired_invite,
    ):
        # Arrange
        mock_invite_repo.get_all_invites.return_value = [valid_invite, expired_invite]

        # Act
        result = await invite_service.get_invites(
            skip=0, limit=10, current_user=current_user
        )

        # Assert
        assert len(result) == 2
        assert result[0].id == valid_invite.id
        assert result[0].is_expired is False
        assert result[0].is_used is False
        assert result[1].id == expired_invite.id
        assert result[1].is_expired is True
        assert result[1].is_used is False

    @pytest.mark.asyncio
    async def test_validate_invite_valid(
        self, invite_service, mock_invite_repo, valid_invite
    ):
        # Arrange
        mock_invite_repo.get_invite_by_token.return_value = valid_invite

        # Act
        result = await invite_service.validate_invite("test-token-12345")

        # Assert
        assert result.valid is True
        assert result.role == "investigator"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_validate_invite_expired(
        self, invite_service, mock_invite_repo, expired_invite
    ):
        # Arrange
        mock_invite_repo.get_invite_by_token.return_value = expired_invite

        # Act
        result = await invite_service.validate_invite("expired-token-12345")

        # Assert
        assert result.valid is False
        assert result.error == "Invite has expired"

    @pytest.mark.asyncio
    async def test_register_user_with_invite_success(
        self, invite_service, mock_invite_repo, mock_user_repo, valid_invite
    ):
        # Arrange
        registration = schemas.UserRegistration(
            username="newuser",
            email="new@test.com",
            password="securepass123",
            token="test-token-12345",
        )

        new_user = models.User(
            id=10,
            username="newuser",
            email="new@test.com",
            role="investigator",
            created_at=datetime.utcnow(),
        )

        mock_invite_repo.get_invite_by_token.return_value = valid_invite
        mock_user_repo.get_user_by_username.return_value = None
        mock_user_repo.get_user_by_email.return_value = None
        mock_user_repo.create_user_from_invite.return_value = new_user

        # Act
        result = await invite_service.register_user_with_invite(registration)

        # Assert
        assert result.id == 10
        assert result.username == "newuser"
        assert result.email == "new@test.com"
        assert result.role == "investigator"

        mock_invite_repo.mark_invite_used.assert_called_once_with(
            invite_service.db, valid_invite
        )

    @pytest.mark.asyncio
    async def test_register_user_with_invalid_invite(
        self, invite_service, mock_invite_repo, mock_user_repo
    ):
        # Arrange
        registration = schemas.UserRegistration(
            username="newuser",
            email="new@test.com",
            password="securepass123",
            token="invalid-token",
        )

        mock_invite_repo.get_invite_by_token.return_value = None

        # Act & Assert
        with pytest.raises(InvalidInviteException) as exc_info:
            await invite_service.register_user_with_invite(registration)

        assert "Invalid invite token" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_register_user_username_taken(
        self, invite_service, mock_invite_repo, mock_user_repo, valid_invite
    ):
        # Arrange
        registration = schemas.UserRegistration(
            username="existinguser",
            email="new@test.com",
            password="securepass123",
            token="test-token-12345",
        )

        mock_invite_repo.get_invite_by_token.return_value = valid_invite
        mock_user_repo.get_user_by_username.return_value = Mock()  # User exists

        # Act & Assert
        with pytest.raises(DuplicateResourceException) as exc_info:
            await invite_service.register_user_with_invite(registration)

        assert str(exc_info.value) == "Username already taken"

    @pytest.mark.asyncio
    async def test_delete_invite_success(
        self, invite_service, mock_invite_repo, mock_db, current_user, valid_invite
    ):
        # Arrange
        mock_db.get.return_value = valid_invite
        mock_invite_repo.delete_invite.return_value = True

        # Act
        result = await invite_service.delete_invite(1, current_user=current_user)

        # Assert
        assert result is True
        mock_invite_repo.delete_invite.assert_called_once_with(
            invite_service.db, invite_id=1
        )

    @pytest.mark.asyncio
    async def test_delete_invite_not_found(
        self, invite_service, mock_invite_repo, mock_db, current_user
    ):
        # Arrange
        mock_db.get.return_value = None

        # Act & Assert
        with pytest.raises(ResourceNotFoundException) as exc_info:
            await invite_service.delete_invite(999, current_user=current_user)

        assert str(exc_info.value) == "Invite not found"

    @pytest.mark.asyncio
    async def test_delete_invite_already_used(
        self, invite_service, mock_invite_repo, mock_db, current_user, used_invite
    ):
        # Arrange
        mock_db.get.return_value = used_invite

        # Act & Assert
        with pytest.raises(InviteException) as exc_info:
            await invite_service.delete_invite(3, current_user=current_user)

        assert str(exc_info.value) == "Cannot delete used invite"

    @pytest.mark.asyncio
    async def test_cleanup_expired_invites(
        self, invite_service, mock_invite_repo, current_user
    ):
        # Arrange
        mock_invite_repo.delete_expired_invites.return_value = 5

        # Act
        result = await invite_service.cleanup_expired_invites(current_user=current_user)

        # Assert
        assert result == 5
        mock_invite_repo.delete_expired_invites.assert_called_once_with(
            invite_service.db
        )


# Performance Tests
class TestPerformance:
    @pytest.mark.asyncio
    async def test_bulk_invite_creation_performance(
        self, invite_service, mock_invite_repo, current_user
    ):
        """Test performance of creating multiple invites"""
        import time

        # Arrange
        mock_invite_repo.create_invite.return_value = Mock(
            id=1, created_at=datetime.utcnow()
        )
        invite_create = schemas.InviteCreate(role="Investigator")

        # Act
        start_time = time.time()
        for _ in range(100):
            await invite_service.create_invite(invite_create, current_user=current_user)
        end_time = time.time()

        # Assert
        execution_time = end_time - start_time
        assert execution_time < 1.0  # Should complete 100 invites in under 1 second
        assert mock_invite_repo.create_invite.call_count == 100

    @pytest.mark.asyncio
    async def test_invite_validation_caching_potential(
        self, invite_service, mock_invite_repo, valid_invite
    ):
        """Test that multiple validations of same token could benefit from caching"""
        # Arrange
        mock_invite_repo.get_invite_by_token.return_value = valid_invite

        # Act
        for _ in range(10):
            await invite_service.validate_invite("test-token-12345")

        # Assert
        assert mock_invite_repo.get_invite_by_token.call_count == 10
        # Note: In production, consider implementing caching to reduce DB calls


# Edge Case Tests
class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_invite_expiration_boundary(self, invite_service, mock_invite_repo):
        """Test invite validation at exact expiration time"""
        # Arrange
        now = datetime.now(timezone.utc).replace(microsecond=0)
        boundary_invite = models.Invite(
            id=1,
            token="boundary-token",
            role="analyst",
            created_at=now - timedelta(hours=24),
            expires_at=now.replace(tzinfo=None),  # Store as naive datetime (DB format)
            used_at=None,
            created_by_id=1,
        )
        mock_invite_repo.get_invite_by_token.return_value = boundary_invite

        # Act
        with patch("app.services.invite_service.get_utc_now", return_value=now):
            result = await invite_service.validate_invite("boundary-token")

        # Assert
        assert result.valid is False
        assert result.error == "Invite has expired"

    @pytest.mark.asyncio
    async def test_concurrent_registration_with_same_invite(
        self, invite_service, mock_invite_repo, mock_user_repo, valid_invite
    ):
        """Test handling of concurrent registrations with same invite token"""
        # Arrange
        registration = schemas.UserRegistration(
            username="user1",
            email="user1@test.com",
            password="password123",
            token="test-token-12345",
        )

        # First call succeeds
        mock_invite_repo.get_invite_by_token.return_value = valid_invite
        mock_user_repo.get_user_by_username.return_value = None
        mock_user_repo.get_user_by_email.return_value = None

        # Create new user mock
        new_user = models.User(
            id=10,
            username="user1",
            email="user1@test.com",
            role="investigator",
            created_at=datetime.utcnow(),
        )
        mock_user_repo.create_user_from_invite.return_value = new_user

        # Act - First registration succeeds
        user1 = await invite_service.register_user_with_invite(registration)
        assert user1.username == "user1"

        # For second registration, simulate that the invite was already used
        used_invite = models.Invite(
            id=valid_invite.id,
            token=valid_invite.token,
            role=valid_invite.role,
            created_at=valid_invite.created_at,
            expires_at=valid_invite.expires_at,
            used_at=datetime.utcnow(),  # Now it's used
            created_by_id=valid_invite.created_by_id,
        )
        mock_invite_repo.get_invite_by_token.return_value = used_invite

        registration2 = schemas.UserRegistration(
            username="user2",
            email="user2@test.com",
            password="password123",
            token="test-token-12345",
        )

        # Assert - Second registration should fail
        with pytest.raises(InvalidInviteException) as exc_info:
            await invite_service.register_user_with_invite(registration2)

        assert "already been used" in str(exc_info.value)
