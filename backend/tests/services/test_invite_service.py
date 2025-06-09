import pytest
from unittest.mock import Mock, patch
from datetime import timedelta
from fastapi import HTTPException
from sqlmodel import Session

from app.services.invite_service import InviteService
from app.database import models
from app.schemas import invite_schema as schemas
from app.core.utils import get_utc_now


class TestInviteService:

    @pytest.fixture(name="invite_service_instance")
    def invite_service_fixture(self, session: Session):
        return InviteService(session)

    def test_init_invite_service(self, session: Session):
        service = InviteService(session)
        assert service.db == session

    @pytest.mark.asyncio
    async def test_create_invite_success(
        self,
        invite_service_instance: InviteService,
        test_admin: models.User,
    ):
        invite_data = schemas.InviteCreate(role="Investigator")

        with patch("app.services.invite_service.crud.create_invite") as mock_create:
            created_invite = Mock()
            created_invite.id = 1
            created_invite.token = "test_token_123"
            created_invite.role = invite_data.role
            created_invite.created_at = get_utc_now()
            created_invite.expires_at = get_utc_now() + timedelta(hours=48)
            created_invite.created_by_id = test_admin.id
            mock_create.return_value = created_invite

            with patch("secrets.token_urlsafe") as mock_token:
                mock_token.return_value = "test_token_123"

                result = await invite_service_instance.create_invite(
                    invite_data, current_user=test_admin
                )

                assert result.role == invite_data.role
                assert result.token == "test_token_123"
                mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_invite_admin_only_permission(
        self,
        invite_service_instance: InviteService,
        test_user: models.User,
    ):
        invite_data = schemas.InviteCreate(role="Investigator")

        with patch("app.core.dependencies.admin_only") as mock_decorator:

            def side_effect(*args, **kwargs):
                if "current_user" in kwargs and kwargs["current_user"].role != "Admin":
                    raise HTTPException(status_code=403, detail="Admin access required")
                return kwargs.get("current_user")

            mock_decorator.return_value = side_effect

            with pytest.raises(HTTPException) as exc_info:
                await invite_service_instance.create_invite(
                    invite_data, current_user=test_user
                )

            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_get_invites_success(
        self,
        invite_service_instance: InviteService,
        test_admin: models.User,
    ):
        with patch(
            "app.services.invite_service.crud.get_invites_by_creator"
        ) as mock_get_invites:
            mock_invite1 = Mock()
            mock_invite1.id = 1
            mock_invite1.role = "Investigator"
            mock_invite1.created_at = get_utc_now() - timedelta(hours=1)
            mock_invite1.expires_at = get_utc_now() + timedelta(hours=47)
            mock_invite1.used_at = None

            mock_invite2 = Mock()
            mock_invite2.id = 2
            mock_invite2.role = "Analyst"
            mock_invite2.created_at = get_utc_now() - timedelta(hours=50)
            mock_invite2.expires_at = get_utc_now() - timedelta(hours=2)
            mock_invite2.used_at = None

            mock_get_invites.return_value = [mock_invite1, mock_invite2]

            result = await invite_service_instance.get_invites(
                current_user=test_admin, skip=0, limit=100
            )

            assert len(result) == 2
            assert result[0].role == "Investigator"
            assert result[0].is_expired == False
            assert result[0].is_used == False
            assert result[1].role == "Analyst"
            assert result[1].is_expired == True
            assert result[1].is_used == False

    @pytest.mark.asyncio
    async def test_validate_invite_success(
        self,
        invite_service_instance: InviteService,
    ):
        token = "valid_token_123"

        with patch(
            "app.services.invite_service.crud.get_invite_by_token"
        ) as mock_get_invite:
            mock_invite = Mock()
            mock_invite.role = "Investigator"
            mock_invite.used_at = None
            mock_invite.expires_at = get_utc_now() + timedelta(hours=24)
            mock_get_invite.return_value = mock_invite

            result = await invite_service_instance.validate_invite(token)

            assert result.valid == True
            assert result.role == "Investigator"
            assert result.error is None

    @pytest.mark.asyncio
    async def test_validate_invite_not_found(
        self,
        invite_service_instance: InviteService,
    ):
        token = "invalid_token"

        with patch(
            "app.services.invite_service.crud.get_invite_by_token"
        ) as mock_get_invite:
            mock_get_invite.return_value = None

            result = await invite_service_instance.validate_invite(token)

            assert result.valid == False
            assert result.error == "Invalid invite token"

    @pytest.mark.asyncio
    async def test_validate_invite_already_used(
        self,
        invite_service_instance: InviteService,
    ):
        token = "used_token_123"

        with patch(
            "app.services.invite_service.crud.get_invite_by_token"
        ) as mock_get_invite:
            mock_invite = Mock()
            mock_invite.used_at = get_utc_now() - timedelta(hours=1)
            mock_get_invite.return_value = mock_invite

            result = await invite_service_instance.validate_invite(token)

            assert result.valid == False
            assert result.error == "Invite has already been used"

    @pytest.mark.asyncio
    async def test_validate_invite_expired(
        self,
        invite_service_instance: InviteService,
    ):
        token = "expired_token_123"

        with patch(
            "app.services.invite_service.crud.get_invite_by_token"
        ) as mock_get_invite:
            mock_invite = Mock()
            mock_invite.used_at = None
            mock_invite.expires_at = get_utc_now() - timedelta(hours=1)
            mock_get_invite.return_value = mock_invite

            result = await invite_service_instance.validate_invite(token)

            assert result.valid == False
            assert result.error == "Invite has expired"

    @pytest.mark.asyncio
    async def test_register_user_with_invite_success(
        self,
        invite_service_instance: InviteService,
    ):
        registration_data = schemas.UserRegistration(
            username="newuser",
            email="newuser@example.com",
            password="password123",
            token="valid_token_123",
        )

        mock_invite = Mock()
        mock_invite.role = "Investigator"
        mock_invite.used_at = None
        mock_invite.expires_at = get_utc_now() + timedelta(hours=24)

        with patch.object(invite_service_instance, "validate_invite") as mock_validate:
            mock_validation = Mock()
            mock_validation.valid = True
            mock_validate.return_value = mock_validation

            with patch(
                "app.services.invite_service.crud.get_invite_by_token"
            ) as mock_get_invite:
                mock_get_invite.return_value = mock_invite

                with patch(
                    "app.services.invite_service.crud.get_user_by_username"
                ) as mock_get_username:
                    mock_get_username.return_value = None

                    with patch(
                        "app.services.invite_service.crud.get_user_by_email"
                    ) as mock_get_email:
                        mock_get_email.return_value = None

                        with patch(
                            "app.services.invite_service.crud.create_user_from_invite"
                        ) as mock_create_user:
                            created_user = Mock()
                            created_user.id = 1
                            created_user.username = registration_data.username
                            created_user.email = registration_data.email
                            created_user.role = mock_invite.role
                            created_user.created_at = get_utc_now()
                            mock_create_user.return_value = created_user

                            with patch(
                                "app.services.invite_service.crud.mark_invite_used"
                            ) as mock_mark_used:
                                mock_mark_used.return_value = mock_invite

                                result = await invite_service_instance.register_user_with_invite(
                                    registration_data
                                )

                                assert result.username == registration_data.username
                                assert result.email == registration_data.email
                                assert result.role == mock_invite.role
                                mock_create_user.assert_called_once()
                                mock_mark_used.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_user_with_invite_invalid_token(
        self,
        invite_service_instance: InviteService,
    ):
        registration_data = schemas.UserRegistration(
            username="newuser",
            email="newuser@example.com",
            password="password123",
            token="invalid_token",
        )

        with patch.object(invite_service_instance, "validate_invite") as mock_validate:
            mock_validation = Mock()
            mock_validation.valid = False
            mock_validation.error = "Invalid invite token"
            mock_validate.return_value = mock_validation

            with pytest.raises(HTTPException) as exc_info:
                await invite_service_instance.register_user_with_invite(
                    registration_data
                )

            assert exc_info.value.status_code == 400
            assert "Invalid invite token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_register_user_with_invite_username_taken(
        self,
        invite_service_instance: InviteService,
    ):
        registration_data = schemas.UserRegistration(
            username="existinguser",
            email="newuser@example.com",
            password="password123",
            token="valid_token_123",
        )

        mock_invite = Mock()
        mock_invite.role = "Investigator"

        with patch.object(invite_service_instance, "validate_invite") as mock_validate:
            mock_validation = Mock()
            mock_validation.valid = True
            mock_validate.return_value = mock_validation

            with patch(
                "app.services.invite_service.crud.get_invite_by_token"
            ) as mock_get_invite:
                mock_get_invite.return_value = mock_invite

                with patch(
                    "app.services.invite_service.crud.get_user_by_username"
                ) as mock_get_username:
                    existing_user = Mock()
                    existing_user.username = registration_data.username
                    mock_get_username.return_value = existing_user

                    with pytest.raises(HTTPException) as exc_info:
                        await invite_service_instance.register_user_with_invite(
                            registration_data
                        )

                    assert exc_info.value.status_code == 400
                    assert "Username already taken" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_register_user_with_invite_email_taken(
        self,
        invite_service_instance: InviteService,
    ):
        registration_data = schemas.UserRegistration(
            username="newuser",
            email="existing@example.com",
            password="password123",
            token="valid_token_123",
        )

        mock_invite = Mock()
        mock_invite.role = "Investigator"

        with patch.object(invite_service_instance, "validate_invite") as mock_validate:
            mock_validation = Mock()
            mock_validation.valid = True
            mock_validate.return_value = mock_validation

            with patch(
                "app.services.invite_service.crud.get_invite_by_token"
            ) as mock_get_invite:
                mock_get_invite.return_value = mock_invite

                with patch(
                    "app.services.invite_service.crud.get_user_by_username"
                ) as mock_get_username:
                    mock_get_username.return_value = None

                    with patch(
                        "app.services.invite_service.crud.get_user_by_email"
                    ) as mock_get_email:
                        existing_user = Mock()
                        existing_user.email = registration_data.email
                        mock_get_email.return_value = existing_user

                        with pytest.raises(HTTPException) as exc_info:
                            await invite_service_instance.register_user_with_invite(
                                registration_data
                            )

                        assert exc_info.value.status_code == 400
                        assert "Email already registered" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_invite_success(
        self,
        invite_service_instance: InviteService,
        test_admin: models.User,
    ):
        invite_id = 1

        mock_invite = Mock()
        mock_invite.id = invite_id
        mock_invite.created_by_id = test_admin.id
        mock_invite.used_at = None

        with patch.object(invite_service_instance.db, "get") as mock_get:
            mock_get.return_value = mock_invite

            with patch("app.services.invite_service.crud.delete_invite") as mock_delete:
                mock_delete.return_value = True

                result = await invite_service_instance.delete_invite(
                    invite_id, current_user=test_admin
                )

                assert result == True
                mock_delete.assert_called_once_with(
                    invite_service_instance.db, invite_id=invite_id
                )

    @pytest.mark.asyncio
    async def test_delete_invite_not_found(
        self,
        invite_service_instance: InviteService,
        test_admin: models.User,
    ):
        invite_id = 999

        with patch.object(invite_service_instance.db, "get") as mock_get:
            mock_get.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await invite_service_instance.delete_invite(
                    invite_id, current_user=test_admin
                )

            assert exc_info.value.status_code == 404
            assert "Invite not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_invite_non_admin_user(
        self,
        invite_service_instance: InviteService,
        test_user: models.User,
    ):
        """Test that non-admin users cannot delete invites"""
        invite_id = 1

        with pytest.raises(HTTPException) as exc_info:
            await invite_service_instance.delete_invite(
                invite_id, current_user=test_user
            )

        assert exc_info.value.status_code == 403
        assert "Not authorized" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_invite_wrong_owner(
        self,
        invite_service_instance: InviteService,
        test_admin: models.User,
    ):
        """Test that admin cannot delete invite created by another admin"""
        invite_id = 1

        # Create another admin user
        other_admin = Mock()
        other_admin.id = 999
        other_admin.role = "Admin"

        mock_invite = Mock()
        mock_invite.id = invite_id
        mock_invite.created_by_id = other_admin.id  # Different from test_admin
        mock_invite.used_at = None

        with patch.object(invite_service_instance.db, "get") as mock_get:
            mock_get.return_value = mock_invite

            with pytest.raises(HTTPException) as exc_info:
                await invite_service_instance.delete_invite(
                    invite_id, current_user=test_admin
                )

            assert exc_info.value.status_code == 403
            assert "Not authorized to delete this invite" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_delete_invite_already_used(
        self,
        invite_service_instance: InviteService,
        test_admin: models.User,
    ):
        invite_id = 1

        mock_invite = Mock()
        mock_invite.id = invite_id
        mock_invite.created_by_id = test_admin.id
        mock_invite.used_at = get_utc_now() - timedelta(hours=1)

        with patch.object(invite_service_instance.db, "get") as mock_get:
            mock_get.return_value = mock_invite

            with pytest.raises(HTTPException) as exc_info:
                await invite_service_instance.delete_invite(
                    invite_id, current_user=test_admin
                )

            assert exc_info.value.status_code == 400
            assert "Cannot delete used invite" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_cleanup_expired_invites_success(
        self,
        invite_service_instance: InviteService,
        test_admin: models.User,
    ):
        with patch(
            "app.services.invite_service.crud.delete_expired_invites"
        ) as mock_cleanup:
            mock_cleanup.return_value = 5  # 5 expired invites cleaned up

            result = await invite_service_instance.cleanup_expired_invites(
                current_user=test_admin
            )

            assert result == 5
            mock_cleanup.assert_called_once_with(invite_service_instance.db)

    @pytest.mark.asyncio
    async def test_cleanup_expired_invites_admin_only(
        self,
        invite_service_instance: InviteService,
        test_user: models.User,
    ):
        with patch("app.core.dependencies.admin_only") as mock_decorator:

            def side_effect(*args, **kwargs):
                if "current_user" in kwargs and kwargs["current_user"].role != "Admin":
                    raise HTTPException(status_code=403, detail="Admin access required")
                return kwargs.get("current_user")

            mock_decorator.return_value = side_effect

            with pytest.raises(HTTPException) as exc_info:
                await invite_service_instance.cleanup_expired_invites(
                    current_user=test_user
                )

            assert exc_info.value.status_code == 403
