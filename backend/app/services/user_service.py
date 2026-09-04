"""Session-backed user lifecycle and privilege policy."""

import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import schemas
from app.core import security, setup
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.exceptions import (
    BaseException as DomainException,
)
from app.core.logging import get_security_logger
from app.core.roles import UserRole
from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import User
from app.services.case_access import CaseAccess

_BOOTSTRAP_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_]{3,50}\Z")


def _validate_user_payload[T: BaseModel](schema: type[T], user_data: object) -> T:
    """Validate an untrusted user payload without leaking validation details."""
    try:
        return schema.model_validate(user_data)
    except PydanticValidationError as error:
        raise ValidationException("Invalid user data") from error


class DuplicateUserField(StrEnum):
    """User identity fields backed by unique database constraints."""

    USERNAME = "username"
    EMAIL = "email"


@dataclass(frozen=True)
class UserIdentity:
    username: str
    email: str
    user_id: int | None = None


class UserService:
    """Own user persistence and the rules governing privileged accounts."""

    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)

    def _find_by_username(self, username: str) -> User | None:
        return self.db.exec(select(User).where(User.username == username)).first()

    def _find_by_email(self, email: str) -> User | None:
        return self.db.exec(select(User).where(User.email == email)).first()

    def _duplicate_field(self, identity: UserIdentity) -> DuplicateUserField | None:
        username_owner = self._find_by_username(identity.username)
        if username_owner is not None and username_owner.id != identity.user_id:
            return DuplicateUserField.USERNAME
        email_owner = self._find_by_email(identity.email)
        if email_owner is not None and email_owner.id != identity.user_id:
            return DuplicateUserField.EMAIL
        return None

    @staticmethod
    def _duplicate_exception(
        field: DuplicateUserField, *, updating: bool = False
    ) -> DuplicateResourceException:
        messages = {
            DuplicateUserField.USERNAME: (
                "Username already taken" if updating else "Username already registered"
            ),
            DuplicateUserField.EMAIL: "Email already registered",
        }
        return DuplicateResourceException(messages[field], field=field.value)

    def _persist_user(
        self,
        user: User,
        identity: UserIdentity,
        *,
        updating: bool,
        invalid_message: str,
    ) -> None:
        """Persist a user and translate a raced unique constraint at its source."""
        try:
            with transaction(self.db):
                self.db.add(user)
                self.db.flush()
        except IntegrityError as error:
            duplicate_field = self._duplicate_field(identity)
            if duplicate_field:
                raise self._duplicate_exception(
                    duplicate_field, updating=updating
                ) from error
            raise ValidationException(invalid_message) from error

    @staticmethod
    def _validate_bootstrap_credentials(user: schemas.BootstrapUserCreate) -> None:
        if not _BOOTSTRAP_USERNAME_PATTERN.fullmatch(user.username):
            raise ValidationException(
                "Username must be 3-50 characters and contain only letters, numbers, and underscores"
            )
        if len(user.password) < 10:
            raise ValidationException("Password must be at least 10 characters")

    def _new_user(self, user: schemas.UserCreate) -> User:
        if user.is_superadmin and user.role != UserRole.ADMIN.value:
            raise ValidationException("Only users with Admin role can be superadmin")
        values = user.model_dump()
        values["password_hash"] = security.get_password_hash(values.pop("password"))
        return User(**values)

    async def create_bootstrap_user(self, user_data: object) -> schemas.User:
        raw_username = (
            user_data.get("username") if isinstance(user_data, dict) else None
        )
        logger = get_security_logger(
            action="create_user",
            target_username=raw_username if isinstance(raw_username, str) else None,
            event_type="user_creation_attempt",
            is_bootstrap=True,
        )
        if not setup.is_setup_required(self.db):
            raise AuthenticationException("Authentication required")
        submitted_token = (
            user_data.get("setup_token") if isinstance(user_data, dict) else None
        )
        if not setup.validate_setup_token(
            submitted_token if isinstance(submitted_token, str) else None
        ):
            logger.bind(
                event_type="user_creation_failed", failure_reason="invalid_setup_token"
            ).warning("Bootstrap user creation failed: invalid setup token")
            raise AuthorizationException("Invalid setup token")

        user = _validate_user_payload(schemas.BootstrapUserCreate, user_data)
        self._validate_bootstrap_credentials(user)
        try:
            with setup.serialize_first_user_creation(self.db):
                if not setup.is_setup_required(self.db):
                    raise AuthorizationException("Setup already completed")
                forced_user = schemas.UserCreate(
                    username=user.username,
                    email=user.email,
                    password=user.password,
                    role=UserRole.ADMIN,
                    is_active=True,
                    is_superadmin=True,
                )
                new_user = self._new_user(forced_user)
                with transaction(self.db):
                    self.db.add(new_user)
                    self.db.flush()
            setup.clear_setup_token()
            logger.bind(
                user_id=new_user.id,
                role=new_user.role,
                event_type="user_creation_success",
            ).info("Bootstrap administrator created successfully")
            return schemas.User.model_validate(new_user)
        except (AuthorizationException, ValidationException):
            raise
        except Exception as error:
            logger.bind(
                event_type="user_creation_error", error_type="system_error"
            ).error(f"Bootstrap user creation error: {error}")
            raise DomainException("Internal server error") from error

    async def create_user_from_payload(
        self, user_data: object, current_user: User
    ) -> schemas.User:
        user = _validate_user_payload(schemas.UserCreate, user_data)
        return await self.create_user(user, current_user)

    async def create_user(
        self, user: schemas.UserCreate, current_user: User
    ) -> schemas.User:
        logger = get_security_logger(
            action="create_user",
            admin_user_id=current_user.id,
            target_username=user.username,
            event_type="user_creation_attempt",
        )
        self.case_access.require_admin(current_user)
        if user.is_superadmin and not current_user.is_superadmin:
            logger.bind(
                event_type="user_creation_failed",
                failure_reason="cannot_create_superadmin",
            ).warning("User creation denied")
            raise AuthorizationException("Only superadmin can create superadmin users")
        identity = UserIdentity(username=user.username, email=str(user.email))
        duplicate_field = self._duplicate_field(identity)
        if duplicate_field:
            logger.bind(
                event_type="user_creation_failed",
                failure_reason=f"duplicate_{duplicate_field.value}",
            ).warning("User creation denied")
            raise self._duplicate_exception(duplicate_field)

        new_user = self._new_user(user)
        self._persist_user(
            new_user, identity, updating=False, invalid_message="Invalid user data"
        )
        logger.bind(user_id=new_user.id, event_type="user_creation_success").info(
            "User created successfully"
        )
        return schemas.User.model_validate(new_user)

    async def get_users(
        self, current_user: User, skip: int = 0, limit: int = 100
    ) -> list[schemas.User]:
        self.case_access.require_admin(current_user)
        users = self.db.exec(select(User).offset(skip).limit(min(limit, 200))).all()
        return [schemas.User.model_validate(user) for user in users]

    async def update_user(
        self, user_id: int, user_update: schemas.UserUpdate, current_user: User
    ) -> schemas.User:
        logger = get_security_logger(
            action="update_user",
            user_id=current_user.id,
            target_user_id=user_id,
            event_type="user_update_attempt",
        )
        is_admin = self.case_access.is_admin(current_user)
        if not is_admin and current_user.id != user_id:
            raise AuthorizationException("Not authorized")
        user = self.db.get(User, user_id)
        if user is None:
            raise ResourceNotFoundException("User not found")
        if user.is_superadmin and not current_user.is_superadmin:
            raise AuthorizationException("Only superadmin can edit superadmin users")
        updates = user_update.model_dump(exclude_unset=True)
        if current_user.id == user_id and not is_admin:
            updates.pop("role", None)
            if updates.pop("is_superadmin", None):
                logger.bind(
                    event_type="user_update_failed",
                    failure_reason="cannot_promote_to_superadmin",
                ).warning("User update denied")
                raise AuthorizationException(
                    "Only superadmin can promote users to superadmin"
                )
        if updates.get("is_superadmin") and not current_user.is_superadmin:
            raise AuthorizationException(
                "Only superadmin can promote users to superadmin"
            )
        final_role = updates.get("role", user.role)
        final_superadmin = updates.get("is_superadmin", user.is_superadmin)
        if final_superadmin and final_role != UserRole.ADMIN.value:
            raise ValidationException("Only users with Admin role can be superadmin")
        username = updates.get("username", user.username)
        email = str(updates.get("email", user.email))
        identity = UserIdentity(username=username, email=email, user_id=user_id)
        duplicate_field = self._duplicate_field(identity)
        if duplicate_field:
            raise self._duplicate_exception(duplicate_field, updating=True)
        updates["updated_at"] = get_utc_now()
        for field, value in updates.items():
            setattr(user, field, value)
        self._persist_user(
            user, identity, updating=True, invalid_message="Invalid update data"
        )
        logger.bind(event_type="user_update_success").info("User updated successfully")
        return schemas.User.model_validate(user)

    async def change_password(
        self, user_id: int, current_password: str, new_password: str, current_user: User
    ) -> schemas.User:
        logger = get_security_logger(
            action="change_password",
            user_id=current_user.id,
            target_user_id=user_id,
            event_type="password_change_attempt",
        )
        user = self.db.get(User, user_id)
        if user is None:
            raise ResourceNotFoundException("User not found")
        if current_user.id != user_id:
            raise AuthorizationException("Not authorized")
        if not security.verify_password(current_password, user.password_hash):
            raise ValidationException("Invalid current password")
        with transaction(self.db):
            user.password_hash = security.get_password_hash(new_password)
            user.updated_at = get_utc_now()
            self.db.add(user)
        logger.bind(event_type="password_change_success").info(
            "Password changed successfully"
        )
        return schemas.User.model_validate(user)

    async def admin_reset_password(
        self, user_id: int, new_password: str, current_user: User
    ) -> schemas.User:
        logger = get_security_logger(
            action="admin_reset_password",
            admin_user_id=current_user.id,
            target_user_id=user_id,
            event_type="admin_password_reset_attempt",
        )
        self.case_access.require_admin(current_user)
        user = self.db.get(User, user_id)
        if user is None:
            raise ResourceNotFoundException("User not found")
        if user.is_superadmin and not current_user.is_superadmin:
            raise AuthorizationException(
                "Only superadmin can reset superadmin passwords"
            )
        with transaction(self.db):
            user.password_hash = security.get_password_hash(new_password)
            user.updated_at = get_utc_now()
            self.db.add(user)
        logger.bind(event_type="admin_password_reset_success").info(
            "Administrator reset password successfully"
        )
        return schemas.User.model_validate(user)

    async def delete_user(self, user_id: int, current_user: User) -> dict:
        logger = get_security_logger(
            action="delete_user",
            user_id=current_user.id,
            target_user_id=user_id,
            event_type="user_deletion_attempt",
        )
        self.case_access.require_admin(current_user)
        user = self.db.get(User, user_id)
        if user is None:
            raise ResourceNotFoundException("User not found")
        if user.is_superadmin:
            raise AuthorizationException("Cannot delete superadmin user")
        if current_user.id == user_id:
            raise AuthorizationException("Cannot delete your own account")
        if user.role == UserRole.ADMIN.value and not current_user.is_superadmin:
            raise AuthorizationException("Only superadmin can delete admin users")
        username = user.username
        with transaction(self.db):
            self.db.delete(user)
        logger.bind(event_type="user_deletion_success").info(
            "User deleted successfully"
        )
        return {"message": f"User '{username}' deleted successfully"}
