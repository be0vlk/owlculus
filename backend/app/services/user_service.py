"""
User management service for Owlculus OSINT platform access control and authentication.

This module handles all user-related business logic including user creation,
profile management, password operations, and role-based access control.
Provides comprehensive user lifecycle management with security validation,
privilege escalation protection, and audit logging for OSINT investigation platforms.
"""

from app import schemas
from app.core.exceptions import (
    AuthorizationException,
    BaseException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.logging import get_security_logger
from app.core.roles import UserRole
from app.database import crud, models
from sqlmodel import Session


class UserService:
    def __init__(self, db: Session):
        self.db = db

    async def create_user(
        self, user: schemas.UserCreate, current_user: models.User
    ) -> schemas.User:
        user_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="create_user",
            target_username=user.username,
            event_type="user_creation_attempt",
        )

        try:
            if await crud.get_user_by_username(self.db, username=user.username):
                user_logger.bind(
                    event_type="user_creation_failed", failure_reason="username_exists"
                ).warning("User creation failed: username already registered")
                raise DuplicateResourceException("Username already registered")

            if await crud.get_user_by_email(self.db, email=user.email):
                user_logger.bind(
                    event_type="user_creation_failed", failure_reason="email_exists"
                ).warning("User creation failed: email already registered")
                raise DuplicateResourceException("Email already registered")

            if user.is_superadmin and not current_user.is_superadmin:
                user_logger.bind(
                    event_type="user_creation_failed",
                    failure_reason="cannot_create_superadmin",
                    target_username=user.username,
                ).warning(
                    "User creation failed: only superadmin can create superadmin users"
                )
                raise AuthorizationException(
                    "Only superadmin can create superadmin users"
                )

            try:
                new_user = await crud.create_user(self.db, user=user)
            except ValueError as e:
                error_msg = str(e).lower()
                if "username already exists" in error_msg:
                    user_logger.bind(
                        event_type="user_creation_failed",
                        failure_reason="username_exists_race",
                    ).warning("User creation failed: username race condition")
                    raise DuplicateResourceException("Username already registered")
                elif "email already exists" in error_msg:
                    user_logger.bind(
                        event_type="user_creation_failed",
                        failure_reason="email_exists_race",
                    ).warning("User creation failed: email race condition")
                    raise DuplicateResourceException("Email already registered")
                else:
                    user_logger.bind(
                        event_type="user_creation_failed",
                        failure_reason="constraint_violation",
                    ).warning(f"User creation failed: {str(e)}")
                    raise ValidationException("Invalid user data")

            user_logger.bind(
                user_id=new_user.id,
                role=new_user.role,
                event_type="user_creation_success",
            ).info("User created successfully")

            return schemas.User.model_validate(new_user)

        except (
            DuplicateResourceException,
            AuthorizationException,
            ValidationException,
        ):
            raise
        except Exception as e:
            user_logger.bind(
                event_type="user_creation_error", error_type="system_error"
            ).error(f"User creation error: {str(e)}")
            raise BaseException("Internal server error")

    async def get_users(
        self, current_user: models.User, skip: int = 0, limit: int = 100
    ) -> list[schemas.User]:
        MAX_LIMIT = 200
        if limit > MAX_LIMIT:
            limit = MAX_LIMIT

        db_users = await crud.get_users(self.db, skip=skip, limit=limit)
        return [schemas.User.model_validate(user) for user in db_users]

    async def update_user(
        self, user_id: int, user_update: schemas.UserUpdate, current_user: models.User
    ) -> schemas.User:
        user_logger = get_security_logger(
            user_id=current_user.id,
            target_user_id=user_id,
            action="update_user",
            event_type="user_update_attempt",
        )

        try:
            if current_user.role != UserRole.ADMIN.value and current_user.id != user_id:
                user_logger.bind(
                    event_type="user_update_failed", failure_reason="not_authorized"
                ).warning("User update failed: not authorized")
                raise AuthorizationException("Not authorized")

            db_user = await crud.get_user(self.db, user_id=user_id)
            if not db_user:
                user_logger.bind(
                    event_type="user_update_failed", failure_reason="user_not_found"
                ).warning("User update failed: user not found")
                raise ResourceNotFoundException("User not found")

            if db_user.is_superadmin and not current_user.is_superadmin:
                user_logger.bind(
                    event_type="user_update_failed",
                    failure_reason="cannot_edit_superadmin",
                    target_username=db_user.username,
                ).warning(
                    "User update failed: only superadmin can edit superadmin users"
                )
                raise AuthorizationException(
                    "Only superadmin can edit superadmin users"
                )

            if user_update.is_superadmin and not current_user.is_superadmin:
                user_logger.bind(
                    event_type="user_update_failed",
                    failure_reason="cannot_promote_to_superadmin",
                    target_username=db_user.username,
                ).warning(
                    "User update failed: only superadmin can promote users to superadmin"
                )
                raise AuthorizationException(
                    "Only superadmin can promote users to superadmin"
                )

            if user_update.username and user_update.username != db_user.username:
                existing_user = await crud.get_user_by_username(
                    self.db, username=user_update.username
                )
                if existing_user:
                    user_logger.bind(
                        event_type="user_update_failed",
                        failure_reason="username_taken",
                        requested_username=user_update.username,
                    ).warning("User update failed: username already taken")
                    raise DuplicateResourceException("Username already taken")

            if user_update.email and user_update.email != db_user.email:
                existing_user = await crud.get_user_by_email(
                    self.db, email=user_update.email
                )
                if existing_user:
                    user_logger.bind(
                        event_type="user_update_failed", failure_reason="email_taken"
                    ).warning("User update failed: email already registered")
                    raise DuplicateResourceException("Email already registered")

            update_data = user_update.model_dump(exclude_unset=True)

            is_self_update = current_user.id == user_id
            is_admin = (
                current_user.role == UserRole.ADMIN.value or current_user.is_superadmin
            )

            if is_self_update and not is_admin:
                if "role" in update_data:
                    user_logger.bind(
                        event_type="privilege_escalation_attempt",
                        attempted_role=update_data["role"],
                    ).warning("User attempted to change their own role")
                    del update_data["role"]

                if "is_superadmin" in update_data:
                    user_logger.bind(
                        event_type="privilege_escalation_attempt",
                        attempted_superadmin=update_data["is_superadmin"],
                    ).warning("User attempted to change their own superadmin status")
                    del update_data["is_superadmin"]

            sanitized_update = schemas.UserUpdate(**update_data)

            try:
                updated_user = await crud.update_user(
                    self.db, user_id=user_id, user=sanitized_update
                )
            except ValueError as e:
                error_msg = str(e).lower()
                if "username already exists" in error_msg:
                    user_logger.bind(
                        event_type="user_update_failed",
                        failure_reason="username_exists_race",
                    ).warning("User update failed: username race condition")
                    raise DuplicateResourceException("Username already taken")
                elif "email already exists" in error_msg:
                    user_logger.bind(
                        event_type="user_update_failed",
                        failure_reason="email_exists_race",
                    ).warning("User update failed: email race condition")
                    raise DuplicateResourceException("Email already registered")
                else:
                    user_logger.bind(
                        event_type="user_update_failed",
                        failure_reason="constraint_violation",
                    ).warning(f"User update failed: {str(e)}")
                    raise ValidationException("Invalid update data")

            user_logger.bind(
                target_user_id=updated_user.id, event_type="user_update_success"
            ).info("User updated successfully")

            return schemas.User.model_validate(updated_user)

        except (
            DuplicateResourceException,
            AuthorizationException,
            ResourceNotFoundException,
            ValidationException,
        ):
            raise
        except Exception as e:
            user_logger.bind(
                event_type="user_update_error", error_type="system_error"
            ).error(f"User update error: {str(e)}")
            raise BaseException("Internal server error")

    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        current_user: models.User,
    ) -> schemas.User:
        user_logger = get_security_logger(
            user_id=current_user.id,
            target_user_id=user_id,
            action="change_password",
            event_type="password_change_attempt",
        )

        try:
            db_user = await crud.get_user(self.db, user_id=user_id)
            if not db_user:
                user_logger.bind(
                    event_type="password_change_failed", failure_reason="user_not_found"
                ).warning("Password change failed: user not found")
                raise ResourceNotFoundException("User not found")

            if current_user.id != user_id:
                user_logger.bind(
                    event_type="password_change_failed", failure_reason="not_authorized"
                ).warning("Password change failed: not authorized")
                raise AuthorizationException("Not authorized")

            updated_user = await crud.change_user_password(
                self.db,
                user=db_user,
                current_password=current_password,
                new_password=new_password,
            )

            user_logger.bind(event_type="password_change_success").info(
                "Password changed successfully"
            )

            return schemas.User.model_validate(updated_user)

        except ValueError as e:
            user_logger.bind(
                event_type="password_change_failed",
                failure_reason="invalid_current_password",
            ).warning(f"Password change failed: {str(e)}")
            raise ValidationException("Invalid current password")
        except (
            DuplicateResourceException,
            AuthorizationException,
            ResourceNotFoundException,
            ValidationException,
        ):
            raise
        except Exception as e:
            user_logger.bind(
                event_type="password_change_error", error_type="system_error"
            ).error(f"Password change error: {str(e)}")
            raise BaseException("Internal server error")

    async def admin_reset_password(
        self, user_id: int, new_password: str, current_user: models.User
    ) -> schemas.User:
        user_logger = get_security_logger(
            admin_user_id=current_user.id,
            target_user_id=user_id,
            action="admin_reset_password",
            event_type="admin_password_reset_attempt",
        )

        try:
            db_user = await crud.get_user(self.db, user_id=user_id)
            if not db_user:
                user_logger.bind(
                    event_type="admin_password_reset_failed",
                    failure_reason="user_not_found",
                ).warning("Admin password reset failed: user not found")
                raise ResourceNotFoundException("User not found")

            if db_user.is_superadmin and not current_user.is_superadmin:
                user_logger.bind(
                    event_type="admin_password_reset_failed",
                    failure_reason="cannot_reset_superadmin_password",
                    target_username=db_user.username,
                ).warning(
                    "Admin password reset failed: only superadmin can reset superadmin passwords"
                )
                raise AuthorizationException(
                    "Only superadmin can reset superadmin passwords"
                )

            updated_user = await crud.admin_reset_password(
                self.db, user=db_user, new_password=new_password
            )

            user_logger.bind(
                target_username=db_user.username,
                event_type="admin_password_reset_success",
            ).info("Admin password reset completed successfully")

            return schemas.User.model_validate(updated_user)

        except (
            DuplicateResourceException,
            AuthorizationException,
            ResourceNotFoundException,
            ValidationException,
        ):
            raise
        except Exception as e:
            user_logger.bind(
                event_type="admin_password_reset_error", error_type="system_error"
            ).error(f"Admin password reset error: {str(e)}")
            raise BaseException("Internal server error")

    async def delete_user(self, user_id: int, current_user: models.User) -> dict:
        user_logger = get_security_logger(
            user_id=current_user.id,
            target_user_id=user_id,
            action="delete_user",
            event_type="user_deletion_attempt",
        )

        try:
            db_user = await crud.get_user(self.db, user_id=user_id)
            if not db_user:
                user_logger.bind(
                    event_type="user_deletion_failed", failure_reason="user_not_found"
                ).warning("User deletion failed: user not found")
                raise ResourceNotFoundException("User not found")

            if db_user.is_superadmin:
                user_logger.bind(
                    event_type="user_deletion_failed",
                    failure_reason="cannot_delete_superadmin",
                    target_username=db_user.username,
                ).warning("User deletion failed: cannot delete superadmin user")
                raise AuthorizationException("Cannot delete superadmin user")

            if current_user.id == user_id:
                user_logger.bind(
                    event_type="user_deletion_failed",
                    failure_reason="self_deletion_attempted",
                ).warning("User deletion failed: cannot delete self")
                raise AuthorizationException("Cannot delete your own account")

            if db_user.role == UserRole.ADMIN.value and not current_user.is_superadmin:
                user_logger.bind(
                    event_type="user_deletion_failed",
                    failure_reason="only_superadmin_can_delete_admin",
                    target_username=db_user.username,
                ).warning(
                    "User deletion failed: only superadmin can delete admin users"
                )
                raise AuthorizationException("Only superadmin can delete admin users")

            username_to_delete = db_user.username
            await crud.delete_user(self.db, user_id=user_id)

            user_logger.bind(
                target_username=username_to_delete, event_type="user_deletion_success"
            ).info("User deleted successfully")

            return {"message": f"User '{username_to_delete}' deleted successfully"}

        except (
            DuplicateResourceException,
            AuthorizationException,
            ResourceNotFoundException,
            ValidationException,
        ):
            raise
        except Exception as e:
            user_logger.bind(
                event_type="user_deletion_error", error_type="system_error"
            ).error(f"User deletion error: {str(e)}")
            raise BaseException("Internal server error")
