"""
Tests for UserService functionality
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi import HTTPException
from sqlmodel import Session

from app.services.user_service import UserService
from app.database import models
from app.schemas import user_schema as schemas
from app.core import security


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
        with patch('app.services.user_service.crud.get_user_by_username') as mock_get_username:
            mock_get_username.return_value = None  # Username not taken
            
            with patch('app.services.user_service.crud.get_user_by_email') as mock_get_email:
                mock_get_email.return_value = None  # Email not taken
                
                with patch('app.services.user_service.crud.create_user') as mock_create:
                    created_user = Mock()
                    created_user.id = 1
                    created_user.username = user_data.username
                    created_user.email = user_data.email
                    created_user.role = user_data.role
                    mock_create.return_value = created_user
                    
                    result = await user_service_instance.create_user(user_data, current_user=test_admin)
                    
                    assert result.username == user_data.username
                    assert result.email == user_data.email
                    assert result.role == user_data.role
                    
                    # Verify all checks were made
                    mock_get_username.assert_called_once_with(user_service_instance.db, username=user_data.username)
                    mock_get_email.assert_called_once_with(user_service_instance.db, email=user_data.email)
                    mock_create.assert_called_once_with(user_service_instance.db, user=user_data)

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
        
        with patch('app.services.user_service.crud.get_user_by_username') as mock_get_username:
            existing_user = Mock()
            existing_user.username = user_data.username
            mock_get_username.return_value = existing_user
            
            with pytest.raises(HTTPException) as exc_info:
                await user_service_instance.create_user(user_data, current_user=test_admin)
            
            assert exc_info.value.status_code == 400
            assert "Username already registered" in exc_info.value.detail

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
        
        with patch('app.services.user_service.crud.get_user_by_username') as mock_get_username:
            mock_get_username.return_value = None
            
            with patch('app.services.user_service.crud.get_user_by_email') as mock_get_email:
                existing_user = Mock()
                existing_user.email = user_data.email
                mock_get_email.return_value = existing_user
                
                with pytest.raises(HTTPException) as exc_info:
                    await user_service_instance.create_user(user_data, current_user=test_admin)
                
                assert exc_info.value.status_code == 400
                assert "Email already registered" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_user_admin_only_permission(
        self,
        user_service_instance: UserService,
        test_user: models.User,  # Non-admin user
    ):
        """Test that only admins can create users"""
        user_data = schemas.UserCreate(
            username="newuser",
            email="newuser@example.com",
            password="password123",
            role="Investigator",
            is_active=True,
        )
        
        # Mock the admin_only decorator to raise exception for non-admin
        with patch('app.core.dependencies.admin_only') as mock_decorator:
            def side_effect(*args, **kwargs):
                if 'current_user' in kwargs and kwargs['current_user'].role != 'Admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                return kwargs.get('current_user')
            
            mock_decorator.return_value = side_effect
            
            with pytest.raises(HTTPException) as exc_info:
                await user_service_instance.create_user(user_data, current_user=test_user)
            
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_users_success(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test successful user listing"""
        skip = 0
        limit = 10
        
        with patch('app.services.user_service.crud.get_users') as mock_get_users:
            mock_users = [Mock(), Mock(), Mock()]
            mock_get_users.return_value = mock_users
            
            result = await user_service_instance.get_users(
                current_user=test_admin, skip=skip, limit=limit
            )
            
            assert result == mock_users
            mock_get_users.assert_called_once_with(user_service_instance.db, skip=skip, limit=limit)

    @pytest.mark.asyncio
    async def test_get_users_admin_only_permission(
        self,
        user_service_instance: UserService,
        test_user: models.User,  # Non-admin user
    ):
        """Test that only admins can list users"""
        with patch('app.core.dependencies.admin_only') as mock_decorator:
            def side_effect(*args, **kwargs):
                if 'current_user' in kwargs and kwargs['current_user'].role != 'Admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                return kwargs.get('current_user')
            
            mock_decorator.return_value = side_effect
            
            with pytest.raises(HTTPException) as exc_info:
                await user_service_instance.get_users(current_user=test_user)
            
            assert exc_info.value.status_code == 403

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
        
        with patch('app.services.user_service.crud.get_user') as mock_get_user:
            existing_user = Mock()
            existing_user.id = user_id
            existing_user.username = "olduser"
            existing_user.email = "old@example.com"
            mock_get_user.return_value = existing_user
            
            with patch('app.services.user_service.crud.get_user_by_username') as mock_get_username:
                mock_get_username.return_value = None  # Username not taken
                
                with patch('app.services.user_service.crud.get_user_by_email') as mock_get_email:
                    mock_get_email.return_value = None  # Email not taken
                    
                    with patch('app.services.user_service.crud.update_user') as mock_update:
                        updated_user = Mock()
                        updated_user.username = user_update.username
                        updated_user.email = user_update.email
                        mock_update.return_value = updated_user
                        
                        result = await user_service_instance.update_user(
                            user_id, user_update, current_user=test_admin
                        )
                        
                        assert result.username == user_update.username
                        assert result.email == user_update.email
                        
                        mock_get_user.assert_called_once_with(user_service_instance.db, user_id=user_id)
                        mock_update.assert_called_once_with(user_service_instance.db, user_id=user_id, user=user_update)

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
        
        with patch('app.services.user_service.crud.get_user') as mock_get_user:
            mock_get_user.return_value = test_user
            
            with patch('app.services.user_service.crud.get_user_by_username') as mock_get_username:
                mock_get_username.return_value = None
                
                with patch('app.services.user_service.crud.get_user_by_email') as mock_get_email:
                    mock_get_email.return_value = None
                    
                    with patch('app.services.user_service.crud.update_user') as mock_update:
                        updated_user = Mock()
                        mock_update.return_value = updated_user
                        
                        result = await user_service_instance.update_user(
                            user_id, user_update, current_user=test_user
                        )
                        
                        assert result == updated_user

    @pytest.mark.asyncio
    async def test_update_user_unauthorized(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test unauthorized user update"""
        other_user_id = 999  # Different from test_user.id
        user_update = schemas.UserUpdate(username="newusername")
        
        with pytest.raises(HTTPException) as exc_info:
            await user_service_instance.update_user(
                other_user_id, user_update, current_user=test_user
            )
        
        assert exc_info.value.status_code == 403
        assert "Not authorized" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_user_not_found(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test updating non-existent user"""
        user_id = 999
        user_update = schemas.UserUpdate(username="newusername")
        
        with patch('app.services.user_service.crud.get_user') as mock_get_user:
            mock_get_user.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await user_service_instance.update_user(
                    user_id, user_update, current_user=test_admin
                )
            
            assert exc_info.value.status_code == 404
            assert "User not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_user_username_taken(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test updating user with taken username"""
        user_id = 2
        user_update = schemas.UserUpdate(username="takenuser")
        
        with patch('app.services.user_service.crud.get_user') as mock_get_user:
            existing_user = Mock()
            existing_user.id = user_id
            existing_user.username = "olduser"
            mock_get_user.return_value = existing_user
            
            with patch('app.services.user_service.crud.get_user_by_username') as mock_get_username:
                conflicting_user = Mock()
                conflicting_user.username = user_update.username
                mock_get_username.return_value = conflicting_user
                
                with pytest.raises(HTTPException) as exc_info:
                    await user_service_instance.update_user(
                        user_id, user_update, current_user=test_admin
                    )
                
                assert exc_info.value.status_code == 400
                assert "Username already taken" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_update_user_email_taken(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test updating user with taken email"""
        user_id = 2
        user_update = schemas.UserUpdate(email="taken@example.com")
        
        with patch('app.services.user_service.crud.get_user') as mock_get_user:
            existing_user = Mock()
            existing_user.id = user_id
            existing_user.email = "old@example.com"
            mock_get_user.return_value = existing_user
            
            with patch('app.services.user_service.crud.get_user_by_email') as mock_get_email:
                conflicting_user = Mock()
                conflicting_user.email = user_update.email
                mock_get_email.return_value = conflicting_user
                
                with pytest.raises(HTTPException) as exc_info:
                    await user_service_instance.update_user(
                        user_id, user_update, current_user=test_admin
                    )
                
                assert exc_info.value.status_code == 400
                assert "Email already registered" in exc_info.value.detail

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
        
        with patch('app.services.user_service.crud.get_user') as mock_get_user:
            mock_get_user.return_value = test_user
            
            with patch('app.services.user_service.crud.change_user_password') as mock_change_password:
                updated_user = Mock()
                mock_change_password.return_value = updated_user
                
                result = await user_service_instance.change_password(
                    user_id, current_password, new_password, current_user=test_user
                )
                
                assert result == updated_user
                mock_get_user.assert_called_once_with(user_service_instance.db, user_id=user_id)
                mock_change_password.assert_called_once_with(
                    user_service_instance.db, user=test_user, 
                    current_password=current_password, new_password=new_password
                )

    @pytest.mark.asyncio
    async def test_change_password_user_not_found(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test password change for non-existent user"""
        user_id = 999
        
        with patch('app.services.user_service.crud.get_user') as mock_get_user:
            mock_get_user.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await user_service_instance.change_password(
                    user_id, "oldpass", "newpass", current_user=test_user
                )
            
            assert exc_info.value.status_code == 404
            assert "User not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_change_password_unauthorized(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test unauthorized password change"""
        other_user_id = 999
        
        with patch('app.services.user_service.crud.get_user') as mock_get_user:
            other_user = Mock()
            other_user.id = other_user_id
            mock_get_user.return_value = other_user
            
            with pytest.raises(HTTPException) as exc_info:
                await user_service_instance.change_password(
                    other_user_id, "oldpass", "newpass", current_user=test_user
                )
            
            assert exc_info.value.status_code == 403
            assert "Not authorized" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_change_password_wrong_current_password(
        self,
        user_service_instance: UserService,
        test_user: models.User,
    ):
        """Test password change with wrong current password"""
        user_id = test_user.id
        
        with patch('app.services.user_service.crud.get_user') as mock_get_user:
            mock_get_user.return_value = test_user
            
            with patch('app.services.user_service.crud.change_user_password') as mock_change_password:
                mock_change_password.side_effect = ValueError("Current password is incorrect")
                
                with pytest.raises(HTTPException) as exc_info:
                    await user_service_instance.change_password(
                        user_id, "wrongpass", "newpass", current_user=test_user
                    )
                
                assert exc_info.value.status_code == 400
                assert "Current password is incorrect" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_admin_reset_password_success(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test successful admin password reset"""
        user_id = 2
        new_password = "resetpassword123"
        
        with patch('app.services.user_service.crud.get_user') as mock_get_user:
            target_user = Mock()
            target_user.id = user_id
            mock_get_user.return_value = target_user
            
            with patch('app.services.user_service.crud.admin_reset_password') as mock_reset:
                updated_user = Mock()
                mock_reset.return_value = updated_user
                
                result = await user_service_instance.admin_reset_password(
                    user_id, new_password, current_user=test_admin
                )
                
                assert result == updated_user
                mock_get_user.assert_called_once_with(user_service_instance.db, user_id=user_id)
                mock_reset.assert_called_once_with(
                    user_service_instance.db, user=target_user, new_password=new_password
                )

    @pytest.mark.asyncio
    async def test_admin_reset_password_user_not_found(
        self,
        user_service_instance: UserService,
        test_admin: models.User,
    ):
        """Test admin password reset for non-existent user"""
        user_id = 999
        
        with patch('app.services.user_service.crud.get_user') as mock_get_user:
            mock_get_user.return_value = None
            
            with pytest.raises(HTTPException) as exc_info:
                await user_service_instance.admin_reset_password(
                    user_id, "newpass", current_user=test_admin
                )
            
            assert exc_info.value.status_code == 404
            assert "User not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_admin_reset_password_admin_only_permission(
        self,
        user_service_instance: UserService,
        test_user: models.User,  # Non-admin user
    ):
        """Test that only admins can reset passwords"""
        with patch('app.core.dependencies.admin_only') as mock_decorator:
            def side_effect(*args, **kwargs):
                if 'current_user' in kwargs and kwargs['current_user'].role != 'Admin':
                    raise HTTPException(status_code=403, detail="Admin access required")
                return kwargs.get('current_user')
            
            mock_decorator.return_value = side_effect
            
            with pytest.raises(HTTPException) as exc_info:
                await user_service_instance.admin_reset_password(
                    999, "newpass", current_user=test_user
                )
            
            assert exc_info.value.status_code == 403