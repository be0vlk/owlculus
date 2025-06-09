"""
User service layer handling all user-related business logic
"""

from sqlmodel import Session
from fastapi import HTTPException

from app.database import models, crud
from app import schemas
from app.core.dependencies import admin_only
from app.core.logging import get_security_logger


class UserService:
    def __init__(self, db: Session):
        self.db = db

    @admin_only()
    async def create_user(
        self, user: schemas.UserCreate, current_user: models.User
    ) -> models.User:
        user_logger = get_security_logger(
            admin_user_id=current_user.id,
            action="create_user",
            target_username=user.username,
            event_type="user_creation_attempt",
        )

        try:
            # Check for existing username
            if await crud.get_user_by_username(self.db, username=user.username):
                user_logger.bind(
                    event_type="user_creation_failed", failure_reason="username_exists"
                ).warning("User creation failed: username already registered")
                raise HTTPException(
                    status_code=400, detail="Username already registered"
                )

            # Check for existing email
            if await crud.get_user_by_email(self.db, email=user.email):
                user_logger.bind(
                    event_type="user_creation_failed", failure_reason="email_exists"
                ).warning("User creation failed: email already registered")
                raise HTTPException(status_code=400, detail="Email already registered")

            # Only superadmin can create superadmin users
            if user.is_superadmin and not current_user.is_superadmin:
                user_logger.bind(
                    event_type="user_creation_failed",
                    failure_reason="cannot_create_superadmin",
                    target_username=user.username,
                ).warning(
                    "User creation failed: only superadmin can create superadmin users"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Only superadmin can create superadmin users",
                )

            new_user = await crud.create_user(self.db, user=user)

            user_logger.bind(
                user_id=new_user.id,
                role=new_user.role,
                event_type="user_creation_success",
            ).info("User created successfully")

            return new_user

        except HTTPException:
            raise
        except Exception as e:
            user_logger.bind(
                event_type="user_creation_error", error_type="system_error"
            ).error(f"User creation error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @admin_only()
    async def get_users(
        self, current_user: models.User, skip: int = 0, limit: int = 100
    ) -> list[models.User]:
        return await crud.get_users(self.db, skip=skip, limit=limit)

    async def update_user(
        self, user_id: int, user_update: schemas.UserUpdate, current_user: models.User
    ) -> models.User:
        user_logger = get_security_logger(
            user_id=current_user.id,
            target_user_id=user_id,
            action="update_user",
            event_type="user_update_attempt",
        )

        try:
            if current_user.role != "Admin" and current_user.id != user_id:
                user_logger.bind(
                    event_type="user_update_failed", failure_reason="not_authorized"
                ).warning("User update failed: not authorized")
                raise HTTPException(status_code=403, detail="Not authorized")

            db_user = await crud.get_user(self.db, user_id=user_id)
            if not db_user:
                user_logger.bind(
                    event_type="user_update_failed", failure_reason="user_not_found"
                ).warning("User update failed: user not found")
                raise HTTPException(status_code=404, detail="User not found")

            # Only superadmin can edit superadmin users
            if db_user.is_superadmin and not current_user.is_superadmin:
                user_logger.bind(
                    event_type="user_update_failed",
                    failure_reason="cannot_edit_superadmin",
                    target_username=db_user.username,
                ).warning(
                    "User update failed: only superadmin can edit superadmin users"
                )
                raise HTTPException(
                    status_code=403, detail="Only superadmin can edit superadmin users"
                )

            # Only superadmin can promote users to superadmin
            if user_update.is_superadmin and not current_user.is_superadmin:
                user_logger.bind(
                    event_type="user_update_failed",
                    failure_reason="cannot_promote_to_superadmin",
                    target_username=db_user.username,
                ).warning(
                    "User update failed: only superadmin can promote users to superadmin"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Only superadmin can promote users to superadmin",
                )

            # Check username uniqueness if being updated
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
                    raise HTTPException(
                        status_code=400, detail="Username already taken"
                    )

            # Check email uniqueness if being updated
            if user_update.email and user_update.email != db_user.email:
                existing_user = await crud.get_user_by_email(
                    self.db, email=user_update.email
                )
                if existing_user:
                    user_logger.bind(
                        event_type="user_update_failed", failure_reason="email_taken"
                    ).warning("User update failed: email already registered")
                    raise HTTPException(
                        status_code=400, detail="Email already registered"
                    )

            updated_user = await crud.update_user(
                self.db, user_id=user_id, user=user_update
            )

            user_logger.bind(
                target_user_id=updated_user.id, event_type="user_update_success"
            ).info("User updated successfully")

            return updated_user

        except HTTPException:
            raise
        except Exception as e:
            user_logger.bind(
                event_type="user_update_error", error_type="system_error"
            ).error(f"User update error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    async def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str,
        current_user: models.User,
    ) -> models.User:
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
                raise HTTPException(status_code=404, detail="User not found")

            if current_user.id != user_id:
                user_logger.bind(
                    event_type="password_change_failed", failure_reason="not_authorized"
                ).warning("Password change failed: not authorized")
                raise HTTPException(status_code=403, detail="Not authorized")

            updated_user = await crud.change_user_password(
                self.db,
                user=db_user,
                current_password=current_password,
                new_password=new_password,
            )

            user_logger.bind(event_type="password_change_success").info(
                "Password changed successfully"
            )

            return updated_user

        except ValueError as e:
            user_logger.bind(
                event_type="password_change_failed",
                failure_reason="invalid_current_password",
            ).warning("Password change failed: invalid current password")
            raise HTTPException(status_code=400, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            user_logger.bind(
                event_type="password_change_error", error_type="system_error"
            ).error(f"Password change error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @admin_only()
    async def admin_reset_password(
        self, user_id: int, new_password: str, current_user: models.User
    ) -> models.User:
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
                raise HTTPException(status_code=404, detail="User not found")

            # Only superadmin can reset superadmin passwords
            if db_user.is_superadmin and not current_user.is_superadmin:
                user_logger.bind(
                    event_type="admin_password_reset_failed",
                    failure_reason="cannot_reset_superadmin_password",
                    target_username=db_user.username,
                ).warning(
                    "Admin password reset failed: only superadmin can reset superadmin passwords"
                )
                raise HTTPException(
                    status_code=403,
                    detail="Only superadmin can reset superadmin passwords",
                )

            updated_user = await crud.admin_reset_password(
                self.db, user=db_user, new_password=new_password
            )

            user_logger.bind(
                target_username=db_user.username,
                event_type="admin_password_reset_success",
            ).info("Admin password reset completed successfully")

            return updated_user

        except HTTPException:
            raise
        except Exception as e:
            user_logger.bind(
                event_type="admin_password_reset_error", error_type="system_error"
            ).error(f"Admin password reset error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

    @admin_only()
    async def delete_user(self, user_id: int, current_user: models.User) -> dict:
        user_logger = get_security_logger(
            user_id=current_user.id,
            target_user_id=user_id,
            action="delete_user",
            event_type="user_deletion_attempt",
        )

        try:
            # Get the user to be deleted
            db_user = await crud.get_user(self.db, user_id=user_id)
            if not db_user:
                user_logger.bind(
                    event_type="user_deletion_failed", failure_reason="user_not_found"
                ).warning("User deletion failed: user not found")
                raise HTTPException(status_code=404, detail="User not found")

            # Prevent deletion of superadmin users
            if db_user.is_superadmin:
                user_logger.bind(
                    event_type="user_deletion_failed",
                    failure_reason="cannot_delete_superadmin",
                    target_username=db_user.username,
                ).warning("User deletion failed: cannot delete superadmin user")
                raise HTTPException(
                    status_code=403, detail="Cannot delete superadmin user"
                )

            # Prevent self-deletion
            if current_user.id == user_id:
                user_logger.bind(
                    event_type="user_deletion_failed",
                    failure_reason="self_deletion_attempted",
                ).warning("User deletion failed: cannot delete self")
                raise HTTPException(
                    status_code=403, detail="Cannot delete your own account"
                )

            # Only superadmin can delete admin users
            if db_user.role == "Admin" and not current_user.is_superadmin:
                user_logger.bind(
                    event_type="user_deletion_failed",
                    failure_reason="only_superadmin_can_delete_admin",
                    target_username=db_user.username,
                ).warning(
                    "User deletion failed: only superadmin can delete admin users"
                )
                raise HTTPException(
                    status_code=403, detail="Only superadmin can delete admin users"
                )

            username_to_delete = db_user.username
            await crud.delete_user(self.db, user_id=user_id)

            user_logger.bind(
                target_username=username_to_delete, event_type="user_deletion_success"
            ).info("User deleted successfully")

            return {"message": f"User '{username_to_delete}' deleted successfully"}

        except HTTPException:
            raise
        except Exception as e:
            user_logger.bind(
                event_type="user_deletion_error", error_type="system_error"
            ).error(f"User deletion error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")
