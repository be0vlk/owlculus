"""
Tests for UserService functionality
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from app.core.exceptions import (
    AuthorizationException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.database import models
from app.schemas import user_schema as schemas
from app.services.user_service import UserService
from sqlmodel import Session


class TestUserService:
    """Test cases for UserService"""

    @pytest.fixture(name="user_service_instance")
    def user_service_fixture(self, session: Session):
        """Create a UserService instance for testing"""
        return UserService(session)

    def test_init_user_service(self, session: Session):
        """Test UserService initialization"""
        service = UserService(session)
        assert service.db == session

    @pytest.mark.asyncio
    async def test_create_user_success(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test successful user creation"""
        user_data = schemas.UserCreate(
            username="newuser",
            email="newuser@example.com",
            password="password123",
            role="Investigator",
            is_active=True,
        )

        # Mock the crud functions
        with patch(
            "app.services.user_service.crud.get_user_by_username"
        ) as mock_get_username:
            mock_get_username.return_value = None  # Username not taken

            with patch(
                "app.services.user_service.crud.get_user_by_email"
            ) as mock_get_email:
                mock_get_email.return_value = None  # Email not taken

                with patch("app.services.user_service.crud.create_user") as mock_create:
                    created_user = Mock()
                    created_user.id = 1
                    created_user.username = user_data.username
                    created_user.email = user_data.email
                    created_user.role = user_data.role
                    created_user.is_active = True
                    created_user.is_superadmin = False
                    created_user.created_at = datetime.utcnow()
                    created_user.updated_at = datetime.utcnow()
                    mock_create.return_value = created_user

                    result = await user_service_instance.create_user(
                        user_data, current_user=test_admin
                    )

                    assert result.username == user_data.username
                    assert result.email == user_data.email
                    assert result.role == user_data.role

                    # Verify all checks were made
                    mock_get_username.assert_called_once_with(
                        user_service_instance.db, username=user_data.username
                    )
                    mock_get_email.assert_called_once_with(
                        user_service_instance.db, email=user_data.email
                    )
                    mock_create.assert_called_once_with(
                        user_service_instance.db, user=user_data
                    )

    @pytest.mark.asyncio
    async def test_create_user_username_exists(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test user creation with existing username"""
        user_data = schemas.UserCreate(
            username="existinguser",
            email="newuser@example.com",
            password="password123",
            role="Investigator",
            is_active=True,
        )

        with patch(
            "app.services.user_service.crud.get_user_by_username"
        ) as mock_get_username:
            existing_user = Mock()
            existing_user.username = user_data.username
            mock_get_username.return_value = existing_user

            with pytest.raises(DuplicateResourceException) as exc_info:
                await user_service_instance.create_user(
                    user_data, current_user=test_admin
                )

            assert "Username already registered" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_user_email_exists(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test user creation with existing email"""
        user_data = schemas.UserCreate(
            username="newuser",
            email="existing@example.com",
            password="password123",
            role="Investigator",
            is_active=True,
        )

        with patch(
            "app.services.user_service.crud.get_user_by_username"
        ) as mock_get_username:
            mock_get_username.return_value = None

            with patch(
                "app.services.user_service.crud.get_user_by_email"
            ) as mock_get_email:
                existing_user = Mock()
                existing_user.email = user_data.email
                mock_get_email.return_value = existing_user

                with pytest.raises(DuplicateResourceException) as exc_info:
                    await user_service_instance.create_user(
                        user_data, current_user=test_admin
                    )

                assert "Email already registered" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_users_success(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test successful user listing"""
        skip = 0
        limit = 10

        with patch("app.services.user_service.crud.get_users") as mock_get_users:
            # Create proper mock users with required attributes
            mock_users = []
            for i in range(3):
                user = Mock()
                user.id = i + 1
                user.username = f"user{i}"
                user.email = f"user{i}@example.com"
                user.role = "Investigator"
                user.is_active = True
                user.is_superadmin = False
                user.created_at = datetime.utcnow()
                user.updated_at = datetime.utcnow()
                mock_users.append(user)

            mock_get_users.return_value = mock_users

            result = await user_service_instance.get_users(
                current_user=test_admin, skip=skip, limit=limit
            )

            assert len(result) == 3
            assert all(isinstance(user, schemas.User) for user in result)
            mock_get_users.assert_called_once_with(
                user_service_instance.db, skip=skip, limit=limit
            )

    @pytest.mark.asyncio
    async def test_update_user_admin_success(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test successful user update by admin"""
        user_id = 2
        user_update = schemas.UserUpdate(
            username="updateduser",
            email="updated@example.com",
            role="Investigator",
        )

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            existing_user = Mock()
            existing_user.id = user_id
            existing_user.username = "olduser"
            existing_user.email = "old@example.com"
            existing_user.is_superadmin = False  # Regular user, not superadmin
            mock_get_user.return_value = existing_user

            with patch(
                "app.services.user_service.crud.get_user_by_username"
            ) as mock_get_username:
                mock_get_username.return_value = None  # Username not taken

                with patch(
                    "app.services.user_service.crud.get_user_by_email"
                ) as mock_get_email:
                    mock_get_email.return_value = None  # Email not taken

                    with patch(
                        "app.services.user_service.crud.update_user"
                    ) as mock_update:
                        updated_user = Mock()
                        updated_user.id = user_id
                        updated_user.username = user_update.username
                        updated_user.email = user_update.email
                        updated_user.role = user_update.role
                        updated_user.is_active = True
                        updated_user.is_superadmin = False
                        updated_user.created_at = datetime.utcnow()
                        updated_user.updated_at = datetime.utcnow()
                        mock_update.return_value = updated_user

                        result = await user_service_instance.update_user(
                            user_id, user_update, current_user=test_admin
                        )

                        assert result.username == user_update.username
                        assert result.email == user_update.email

                        mock_get_user.assert_called_once_with(
                            user_service_instance.db, user_id=user_id
                        )
                        # Note: The actual call now passes a sanitized update
                        mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_self_success(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test successful self user update"""
        user_id = test_user.id
        user_update = schemas.UserUpdate(
            username="newusername",
            email="newemail@example.com",
        )

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = test_user

            with patch(
                "app.services.user_service.crud.get_user_by_username"
            ) as mock_get_username:
                mock_get_username.return_value = None

                with patch(
                    "app.services.user_service.crud.get_user_by_email"
                ) as mock_get_email:
                    mock_get_email.return_value = None

                    with patch(
                        "app.services.user_service.crud.update_user"
                    ) as mock_update:
                        updated_user = Mock()
                        updated_user.id = user_id
                        updated_user.username = user_update.username
                        updated_user.email = user_update.email
                        updated_user.role = "Investigator"  # Should keep valid role
                        updated_user.is_active = True
                        updated_user.is_superadmin = False
                        updated_user.created_at = datetime.utcnow()
                        updated_user.updated_at = datetime.utcnow()
                        mock_update.return_value = updated_user

                        result = await user_service_instance.update_user(
                            user_id, user_update, current_user=test_user
                        )

                        assert isinstance(result, schemas.User)
                        assert result.username == user_update.username

    @pytest.mark.asyncio
    async def test_update_user_self_privilege_escalation_prevented(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test that users cannot escalate their own privileges"""
        user_id = test_user.id
        user_update = schemas.UserUpdate(
            username="newusername",
            role="Admin",  # Attempting to become admin
            is_superadmin=True,  # Attempting to become superadmin
        )

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = test_user

            # Test that the attempt to escalate privileges is blocked
            with pytest.raises(AuthorizationException) as exc_info:
                await user_service_instance.update_user(
                    user_id, user_update, current_user=test_user
                )

            assert "Only superadmin can promote users to superadmin" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_update_user_self_role_escalation_prevented(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test that non-admin users cannot change their own role (without superadmin attempt)"""
        user_id = test_user.id
        user_update = schemas.UserUpdate(
            username="newusername",
            role="Admin",  # Attempting to become admin (but not superadmin)
        )

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = test_user

            with patch(
                "app.services.user_service.crud.get_user_by_username"
            ) as mock_get_username:
                mock_get_username.return_value = None

                with patch("app.services.user_service.crud.update_user") as mock_update:
                    # The mock should return a user without role escalation
                    updated_user = Mock()
                    updated_user.id = user_id
                    updated_user.username = user_update.username
                    updated_user.email = test_user.email
                    updated_user.role = (
                        "Investigator"  # Use a valid role from the schema
                    )
                    updated_user.is_active = True
                    updated_user.is_superadmin = False
                    updated_user.created_at = datetime.utcnow()
                    updated_user.updated_at = datetime.utcnow()
                    mock_update.return_value = updated_user

                    result = await user_service_instance.update_user(
                        user_id, user_update, current_user=test_user
                    )

                    # Verify the user was updated but role was not escalated
                    assert isinstance(result, schemas.User)
                    assert result.username == user_update.username
                    assert (
                        result.role == "Investigator"
                    )  # Role unchanged from sanitization

                    # Verify the update was called with sanitized data
                    mock_update.assert_called_once()
                    args, kwargs = mock_update.call_args
                    sanitized_update = kwargs.get("user") or args[2]
                    # The sanitized update should not contain role
                    update_dict = sanitized_update.model_dump(exclude_unset=True)
                    assert "role" not in update_dict

    @pytest.mark.asyncio
    async def test_update_user_unauthorized(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test unauthorized user update"""
        other_user_id = 999  # Different from test_user.id
        user_update = schemas.UserUpdate(username="newusername")

        with pytest.raises(AuthorizationException) as exc_info:
            await user_service_instance.update_user(
                other_user_id, user_update, current_user=test_user
            )

        assert "Not authorized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_user_not_found(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test updating non-existent user"""
        user_id = 999
        user_update = schemas.UserUpdate(username="newusername")

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(ResourceNotFoundException) as exc_info:
                await user_service_instance.update_user(
                    user_id, user_update, current_user=test_admin
                )

            assert "User not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_user_username_taken(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test updating user with taken username"""
        user_id = 2
        user_update = schemas.UserUpdate(username="takenuser")

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            existing_user = Mock()
            existing_user.id = user_id
            existing_user.username = "olduser"
            existing_user.is_superadmin = False  # Regular user, not superadmin
            mock_get_user.return_value = existing_user

            with patch(
                "app.services.user_service.crud.get_user_by_username"
            ) as mock_get_username:
                conflicting_user = Mock()
                conflicting_user.username = user_update.username
                mock_get_username.return_value = conflicting_user

                with pytest.raises(DuplicateResourceException) as exc_info:
                    await user_service_instance.update_user(
                        user_id, user_update, current_user=test_admin
                    )

                assert "Username already taken" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_user_email_taken(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test updating user with taken email"""
        user_id = 2
        user_update = schemas.UserUpdate(email="taken@example.com")

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            existing_user = Mock()
            existing_user.id = user_id
            existing_user.email = "old@example.com"
            existing_user.is_superadmin = False  # Regular user, not superadmin
            mock_get_user.return_value = existing_user

            with patch(
                "app.services.user_service.crud.get_user_by_email"
            ) as mock_get_email:
                conflicting_user = Mock()
                conflicting_user.email = user_update.email
                mock_get_email.return_value = conflicting_user

                with pytest.raises(DuplicateResourceException) as exc_info:
                    await user_service_instance.update_user(
                        user_id, user_update, current_user=test_admin
                    )

                assert "Email already registered" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_change_password_success(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test successful password change"""
        user_id = test_user.id
        current_password = "oldpassword"
        new_password = "newpassword123"

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = test_user

            with patch(
                "app.services.user_service.crud.change_user_password"
            ) as mock_change_password:
                updated_user = Mock()
                updated_user.id = user_id
                updated_user.username = test_user.username
                updated_user.email = test_user.email
                updated_user.role = "Investigator"  # Use valid role
                updated_user.is_active = True
                updated_user.is_superadmin = False
                updated_user.password_hash = "$2b$12$hashedpassword"
                updated_user.created_at = datetime.utcnow()
                updated_user.updated_at = datetime.utcnow()
                mock_change_password.return_value = updated_user

                result = await user_service_instance.change_password(
                    user_id, current_password, new_password, current_user=test_user
                )

                assert isinstance(result, schemas.User)
                mock_get_user.assert_called_once_with(
                    user_service_instance.db, user_id=user_id
                )
                mock_change_password.assert_called_once_with(
                    user_service_instance.db,
                    user=test_user,
                    current_password=current_password,
                    new_password=new_password,
                )

    @pytest.mark.asyncio
    async def test_change_password_user_not_found(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test password change for non-existent user"""
        user_id = 999

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(ResourceNotFoundException) as exc_info:
                await user_service_instance.change_password(
                    user_id, "oldpass", "newpass", current_user=test_user
                )

            assert "User not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_change_password_unauthorized(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test unauthorized password change"""
        other_user_id = 999

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            other_user = Mock()
            other_user.id = other_user_id
            mock_get_user.return_value = other_user

            with pytest.raises(AuthorizationException) as exc_info:
                await user_service_instance.change_password(
                    other_user_id, "oldpass", "newpass", current_user=test_user
                )

            assert "Not authorized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_change_password_wrong_current_password(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test password change with wrong current password"""
        user_id = test_user.id

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = test_user

            with patch(
                "app.services.user_service.crud.change_user_password"
            ) as mock_change_password:
                mock_change_password.side_effect = ValueError(
                    "Current password is incorrect"
                )

                with pytest.raises(ValidationException) as exc_info:
                    await user_service_instance.change_password(
                        user_id, "wrongpass", "newpass", current_user=test_user
                    )

                assert "Invalid current password" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_admin_reset_password_success(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test successful admin password reset"""
        user_id = 2
        new_password = "resetpassword123"

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            target_user = Mock()
            target_user.id = user_id
            target_user.is_superadmin = False  # Regular user, not superadmin
            mock_get_user.return_value = target_user

            with patch(
                "app.services.user_service.crud.admin_reset_password"
            ) as mock_reset:
                updated_user = Mock()
                updated_user.id = user_id
                updated_user.username = "targetuser"
                updated_user.email = "target@example.com"
                updated_user.role = "Investigator"
                updated_user.is_active = True
                updated_user.is_superadmin = False
                updated_user.created_at = datetime.utcnow()
                updated_user.updated_at = datetime.utcnow()
                mock_reset.return_value = updated_user

                result = await user_service_instance.admin_reset_password(
                    user_id, new_password, current_user=test_admin
                )

                assert isinstance(result, schemas.User)
                mock_get_user.assert_called_once_with(
                    user_service_instance.db, user_id=user_id
                )
                mock_reset.assert_called_once_with(
                    user_service_instance.db,
                    user=target_user,
                    new_password=new_password,
                )

    @pytest.mark.asyncio
    async def test_admin_reset_password_user_not_found(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test admin password reset for non-existent user"""
        user_id = 999

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(ResourceNotFoundException) as exc_info:
                await user_service_instance.admin_reset_password(
                    user_id, "newpass", current_user=test_admin
                )

            assert "User not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_user_success_superadmin_deletes_regular_user(
        self,
        user_service_instance: UserService,
    ):
        """Test successful user deletion by superadmin"""
        # Create superadmin user
        superadmin = Mock()
        superadmin.id = 1
        superadmin.role = "Admin"
        superadmin.is_superadmin = True

        # Create regular user to delete
        target_user = Mock()
        target_user.id = 2
        target_user.username = "regularuser"
        target_user.role = "Investigator"
        target_user.is_superadmin = False

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = target_user

            with patch("app.services.user_service.crud.delete_user") as mock_delete:
                mock_delete.return_value = True

                result = await user_service_instance.delete_user(
                    target_user.id, current_user=superadmin
                )

                assert "deleted successfully" in result["message"]
                mock_get_user.assert_called_once_with(
                    user_service_instance.db, user_id=target_user.id
                )
                mock_delete.assert_called_once_with(
                    user_service_instance.db, user_id=target_user.id
                )

    @pytest.mark.asyncio
    async def test_delete_user_success_superadmin_deletes_admin(
        self,
        user_service_instance: UserService,
    ):
        """Test successful admin deletion by superadmin"""
        # Create superadmin user
        superadmin = Mock()
        superadmin.id = 1
        superadmin.role = "Admin"
        superadmin.is_superadmin = True

        # Create admin user to delete
        target_admin = Mock()
        target_admin.id = 2
        target_admin.username = "adminuser"
        target_admin.role = "Admin"
        target_admin.is_superadmin = False

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = target_admin

            with patch("app.services.user_service.crud.delete_user") as mock_delete:
                mock_delete.return_value = True

                result = await user_service_instance.delete_user(
                    target_admin.id, current_user=superadmin
                )

                assert "deleted successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_delete_user_success_admin_deletes_regular_user(
        self,
        user_service_instance: UserService,
    ):
        """Test successful regular user deletion by regular admin"""
        # Create regular admin user
        admin = Mock()
        admin.id = 1
        admin.role = "Admin"
        admin.is_superadmin = False

        # Create regular user to delete
        target_user = Mock()
        target_user.id = 2
        target_user.username = "regularuser"
        target_user.role = "Investigator"
        target_user.is_superadmin = False

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = target_user

            with patch("app.services.user_service.crud.delete_user") as mock_delete:
                mock_delete.return_value = True

                result = await user_service_instance.delete_user(
                    target_user.id, current_user=admin
                )

                assert "deleted successfully" in result["message"]

    @pytest.mark.asyncio
    async def test_delete_user_cannot_delete_superadmin(
        self,
        user_service_instance: UserService,
    ):
        """Test that superadmin users cannot be deleted"""
        # Create superadmin user
        superadmin = Mock()
        superadmin.id = 1
        superadmin.role = "Admin"
        superadmin.is_superadmin = True

        # Create superadmin user to delete
        target_superadmin = Mock()
        target_superadmin.id = 2
        target_superadmin.username = "superadmin2"
        target_superadmin.role = "Admin"
        target_superadmin.is_superadmin = True

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = target_superadmin

            with pytest.raises(AuthorizationException) as exc_info:
                await user_service_instance.delete_user(
                    target_superadmin.id, current_user=superadmin
                )

            assert "Cannot delete superadmin user" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_user_cannot_delete_self(
        self,
        user_service_instance: UserService,
    ):
        """Test that users cannot delete themselves"""
        # Create regular admin user (not superadmin) to avoid superadmin protection
        admin = Mock()
        admin.id = 1
        admin.role = "Admin"
        admin.is_superadmin = False

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = admin

            with pytest.raises(AuthorizationException) as exc_info:
                await user_service_instance.delete_user(admin.id, current_user=admin)

            assert "Cannot delete your own account" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_user_admin_cannot_delete_admin(
        self,
        user_service_instance: UserService,
    ):
        """Test that regular admin cannot delete other admin users"""
        # Create regular admin user
        admin = Mock()
        admin.id = 1
        admin.role = "Admin"
        admin.is_superadmin = False

        # Create admin user to delete
        target_admin = Mock()
        target_admin.id = 2
        target_admin.username = "adminuser"
        target_admin.role = "Admin"
        target_admin.is_superadmin = False

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = target_admin

            with pytest.raises(AuthorizationException) as exc_info:
                await user_service_instance.delete_user(
                    target_admin.id, current_user=admin
                )

            assert "Only superadmin can delete admin users" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_delete_user_not_found(
        self,
        user_service_instance: UserService,
    ):
        """Test deleting non-existent user"""
        # Create superadmin user
        superadmin = Mock()
        superadmin.id = 1
        superadmin.role = "Admin"
        superadmin.is_superadmin = True

        user_id = 999

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(ResourceNotFoundException) as exc_info:
                await user_service_instance.delete_user(
                    user_id, current_user=superadmin
                )

            assert "User not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_admin_reset_password_cannot_reset_superadmin(
        self,
        user_service_instance: UserService,
    ):
        """Test that regular admin cannot reset superadmin password"""
        # Create regular admin user
        admin = Mock()
        admin.id = 1
        admin.role = "Admin"
        admin.is_superadmin = False

        # Create superadmin user to reset password
        superadmin_target = Mock()
        superadmin_target.id = 2
        superadmin_target.username = "superadmin"
        superadmin_target.role = "Admin"
        superadmin_target.is_superadmin = True

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = superadmin_target

            with pytest.raises(AuthorizationException) as exc_info:
                await user_service_instance.admin_reset_password(
                    superadmin_target.id, "newpassword", current_user=admin
                )

            assert "Only superadmin can reset superadmin passwords" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_admin_reset_password_superadmin_can_reset_superadmin(
        self,
        user_service_instance: UserService,
    ):
        """Test that superadmin can reset another superadmin password"""
        # Create superadmin user
        superadmin = Mock()
        superadmin.id = 1
        superadmin.role = "Admin"
        superadmin.is_superadmin = True

        # Create superadmin user to reset password
        superadmin_target = Mock()
        superadmin_target.id = 2
        superadmin_target.username = "superadmin2"
        superadmin_target.role = "Admin"
        superadmin_target.is_superadmin = True

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = superadmin_target

            with patch(
                "app.services.user_service.crud.admin_reset_password"
            ) as mock_reset:
                updated_user = Mock()
                updated_user.id = superadmin_target.id
                updated_user.username = superadmin_target.username
                updated_user.email = "super2@example.com"
                updated_user.role = superadmin_target.role
                updated_user.is_active = True
                updated_user.is_superadmin = True
                updated_user.created_at = datetime.utcnow()
                updated_user.updated_at = datetime.utcnow()
                mock_reset.return_value = updated_user

                result = await user_service_instance.admin_reset_password(
                    superadmin_target.id, "newpassword", current_user=superadmin
                )

                assert isinstance(result, schemas.User)
                mock_reset.assert_called_once_with(
                    user_service_instance.db,
                    user=superadmin_target,
                    new_password="newpassword",
                )

    @pytest.mark.asyncio
    async def test_update_user_admin_cannot_edit_superadmin(
        self,
        user_service_instance: UserService,
    ):
        """Test that regular admin cannot edit superadmin users"""
        # Create regular admin user
        admin = Mock()
        admin.id = 1
        admin.role = "Admin"
        admin.is_superadmin = False

        # Create superadmin user to edit
        superadmin_target = Mock()
        superadmin_target.id = 2
        superadmin_target.username = "superadmin"
        superadmin_target.role = "Admin"
        superadmin_target.is_superadmin = True

        user_update = schemas.UserUpdate(username="newsuperadmin")

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = superadmin_target

            with pytest.raises(AuthorizationException) as exc_info:
                await user_service_instance.update_user(
                    superadmin_target.id, user_update, current_user=admin
                )

            assert "Only superadmin can edit superadmin users" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_user_superadmin_can_edit_superadmin(
        self,
        user_service_instance: UserService,
    ):
        """Test that superadmin can edit another superadmin user"""
        # Create superadmin user
        superadmin = Mock()
        superadmin.id = 1
        superadmin.role = "Admin"
        superadmin.is_superadmin = True

        # Create superadmin user to edit
        superadmin_target = Mock()
        superadmin_target.id = 2
        superadmin_target.username = "superadmin2"
        superadmin_target.email = "super2@example.com"
        superadmin_target.role = "Admin"
        superadmin_target.is_superadmin = True

        user_update = schemas.UserUpdate(username="newsuperadmin")

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = superadmin_target

            with patch(
                "app.services.user_service.crud.get_user_by_username"
            ) as mock_get_username:
                mock_get_username.return_value = None  # Username not taken

                with patch(
                    "app.services.user_service.crud.get_user_by_email"
                ) as mock_get_email:
                    mock_get_email.return_value = None  # Email not taken

                    with patch(
                        "app.services.user_service.crud.update_user"
                    ) as mock_update:
                        updated_user = Mock()
                        updated_user.id = superadmin_target.id
                        updated_user.username = user_update.username
                        updated_user.email = superadmin_target.email
                        updated_user.role = superadmin_target.role
                        updated_user.is_active = True
                        updated_user.is_superadmin = True
                        updated_user.created_at = datetime.utcnow()
                        updated_user.updated_at = datetime.utcnow()
                        mock_update.return_value = updated_user

                        result = await user_service_instance.update_user(
                            superadmin_target.id, user_update, current_user=superadmin
                        )

                        assert result.username == user_update.username
                        # The actual call is made with sanitized update
                        mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_admin_cannot_create_superadmin(
        self,
        user_service_instance: UserService,
    ):
        """Test that regular admin cannot create superadmin users"""
        # Create regular admin user
        admin = Mock()
        admin.id = 1
        admin.role = "Admin"
        admin.is_superadmin = False

        user_data = schemas.UserCreate(
            username="newsuperadmin",
            email="newsuperadmin@example.com",
            password="password123",
            role="Admin",
            is_active=True,
            is_superadmin=True,  # Attempting to create superadmin
        )

        with patch(
            "app.services.user_service.crud.get_user_by_username"
        ) as mock_get_username:
            mock_get_username.return_value = None  # Username not taken

            with patch(
                "app.services.user_service.crud.get_user_by_email"
            ) as mock_get_email:
                mock_get_email.return_value = None  # Email not taken

                with pytest.raises(AuthorizationException) as exc_info:
                    await user_service_instance.create_user(
                        user_data, current_user=admin
                    )

                assert "Only superadmin can create superadmin users" in str(
                    exc_info.value
                )

    @pytest.mark.asyncio
    async def test_create_user_superadmin_can_create_superadmin(
        self,
        user_service_instance: UserService,
    ):
        """Test that superadmin can create superadmin users"""
        # Create superadmin user
        superadmin = Mock()
        superadmin.id = 1
        superadmin.role = "Admin"
        superadmin.is_superadmin = True

        user_data = schemas.UserCreate(
            username="newsuperadmin",
            email="newsuperadmin@example.com",
            password="password123",
            role="Admin",
            is_active=True,
            is_superadmin=True,
        )

        with patch(
            "app.services.user_service.crud.get_user_by_username"
        ) as mock_get_username:
            mock_get_username.return_value = None  # Username not taken

            with patch(
                "app.services.user_service.crud.get_user_by_email"
            ) as mock_get_email:
                mock_get_email.return_value = None  # Email not taken

                with patch("app.services.user_service.crud.create_user") as mock_create:
                    created_user = Mock()
                    created_user.id = 2
                    created_user.username = user_data.username
                    created_user.email = user_data.email
                    created_user.role = user_data.role
                    created_user.is_active = True
                    created_user.is_superadmin = True
                    created_user.password_hash = "$2b$12$hashedpassword"
                    created_user.created_at = datetime.utcnow()
                    created_user.updated_at = datetime.utcnow()
                    mock_create.return_value = created_user

                    result = await user_service_instance.create_user(
                        user_data, current_user=superadmin
                    )

                    assert result.username == user_data.username
                    assert result.role == "Admin"  # Superadmins must have Admin role
                    mock_create.assert_called_once_with(
                        user_service_instance.db, user=user_data
                    )

    @pytest.mark.asyncio
    async def test_update_user_admin_cannot_promote_to_superadmin(
        self,
        user_service_instance: UserService,
    ):
        """Test that regular admin cannot promote users to superadmin"""
        # Create regular admin user
        admin = Mock()
        admin.id = 1
        admin.role = "Admin"
        admin.is_superadmin = False

        # Create regular user to promote
        target_user = Mock()
        target_user.id = 2
        target_user.username = "regularuser"
        target_user.email = "regular@example.com"
        target_user.role = "Investigator"
        target_user.is_superadmin = False

        user_update = schemas.UserUpdate(is_superadmin=True)

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = target_user

            with pytest.raises(AuthorizationException) as exc_info:
                await user_service_instance.update_user(
                    target_user.id, user_update, current_user=admin
                )

            assert "Only superadmin can promote users to superadmin" in str(
                exc_info.value
            )

    @pytest.mark.asyncio
    async def test_update_user_superadmin_can_promote_to_superadmin(
        self,
        user_service_instance: UserService,
    ):
        """Test that superadmin can promote users to superadmin"""
        # Create superadmin user
        superadmin = Mock()
        superadmin.id = 1
        superadmin.role = "Admin"
        superadmin.is_superadmin = True

        # Create regular user to promote
        target_user = Mock()
        target_user.id = 2
        target_user.username = "regularuser"
        target_user.email = "regular@example.com"
        target_user.role = "Investigator"
        target_user.is_superadmin = False

        user_update = schemas.UserUpdate(is_superadmin=True)

        with patch("app.services.user_service.crud.get_user") as mock_get_user:
            mock_get_user.return_value = target_user

            with patch(
                "app.services.user_service.crud.get_user_by_username"
            ) as mock_get_username:
                mock_get_username.return_value = None  # Username not taken

                with patch(
                    "app.services.user_service.crud.get_user_by_email"
                ) as mock_get_email:
                    mock_get_email.return_value = None  # Email not taken

                    with patch(
                        "app.services.user_service.crud.update_user"
                    ) as mock_update:
                        updated_user = Mock()
                        updated_user.id = target_user.id
                        updated_user.username = target_user.username
                        updated_user.email = target_user.email
                        updated_user.role = target_user.role
                        updated_user.is_active = True
                        updated_user.is_superadmin = True
                        updated_user.created_at = datetime.utcnow()
                        updated_user.updated_at = datetime.utcnow()
                        mock_update.return_value = updated_user

                        result = await user_service_instance.update_user(
                            target_user.id, user_update, current_user=superadmin
                        )

                        assert isinstance(result, schemas.User)
                        # The actual call is made with sanitized update
                        mock_update.assert_called_once()
