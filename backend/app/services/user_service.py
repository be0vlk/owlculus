"""Session-backed user lifecycle and privilege policy."""

import re

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


class UserService:
    """Own user persistence and the rules governing privileged accounts."""

    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)

    def _find_by_username(self, username: str) -> User | None:
        return self.db.exec(select(User).where(User.username == username)).first()

    def _find_by_email(self, email: str) -> User | None:
        return self.db.exec(select(User).where(User.email == email)).first()

    def _duplicate_field(
        self, *, username: str, email: str, exclude_user_id: int | None = None
    ) -> str | None:
        username_owner = self._find_by_username(username)
        if username_owner is not None and username_owner.id != exclude_user_id:
            return "username"
        email_owner = self._find_by_email(email)
        if email_owner is not None and email_owner.id != exclude_user_id:
            return "email"
        return None

    @staticmethod
    def _raise_duplicate(field: str, *, updating: bool = False) -> None:
        messages = {
            "username": (
                "Username already taken" if updating else "Username already registered"
            ),
            "email": "Email already registered",
        }
        raise DuplicateResourceException(messages[field], field=field)

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
        self.case_access.require_admin(current_user)
        if user.is_superadmin and not current_user.is_superadmin:
            raise AuthorizationException("Only superadmin can create superadmin users")
        duplicate_field = self._duplicate_field(
            username=user.username, email=str(user.email)
        )
        if duplicate_field:
            self._raise_duplicate(duplicate_field)

        new_user = self._new_user(user)
        try:
            with transaction(self.db):
                self.db.add(new_user)
                self.db.flush()
        except IntegrityError as error:
            duplicate_field = self._duplicate_field(
                username=user.username, email=str(user.email)
            )
            if duplicate_field:
                self._raise_duplicate(duplicate_field)
            raise ValidationException("Invalid user data") from error
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
            updates.pop("is_superadmin", None)
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
        duplicate_field = self._duplicate_field(
            username=username, email=email, exclude_user_id=user_id
        )
        if duplicate_field:
            self._raise_duplicate(duplicate_field, updating=True)
        for field, value in updates.items():
            setattr(user, field, value)
        try:
            with transaction(self.db):
                self.db.add(user)
                self.db.flush()
        except IntegrityError as error:
            duplicate_field = self._duplicate_field(
                username=username, email=email, exclude_user_id=user_id
            )
            if duplicate_field:
                self._raise_duplicate(duplicate_field, updating=True)
            raise ValidationException("Invalid update data") from error
        return schemas.User.model_validate(user)

    async def change_password(
        self, user_id: int, current_password: str, new_password: str, current_user: User
    ) -> schemas.User:
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
        return schemas.User.model_validate(user)

    async def admin_reset_password(
        self, user_id: int, new_password: str, current_user: User
    ) -> schemas.User:
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
        return schemas.User.model_validate(user)

    async def delete_user(self, user_id: int, current_user: User) -> dict:
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
        return {"message": f"User '{username}' deleted successfully"}
