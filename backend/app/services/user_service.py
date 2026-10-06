"""Session-backed user lifecycle and privilege policy."""

import re

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app import schemas
from app.core import security, setup
from app.core.enums import UserRole
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    DomainException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.logging import audit_operation, get_security_logger
from app.core.utils import get_utc_now
from app.database.db_utils import transaction
from app.database.models import CaseUserLink, User
from app.services.case_access import CaseAccess

_BOOTSTRAP_USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_]{3,50}\Z")


def _validate_user_payload[T: BaseModel](schema: type[T], user_data: object) -> T:
    """Validate an untrusted user payload without leaking validation details."""
    try:
        return schema.model_validate(user_data)
    except PydanticValidationError as error:
        raise ValidationException("Invalid user data") from error


def duplicate_user_error(
    db: Session,
    username: str,
    email: str,
    exclude_id: int | None = None,
    username_message: str = "Username already taken",
) -> DuplicateResourceException | None:
    """Name the first identity field another user already owns."""
    for field, value, message in (
        ("username", username, username_message),
        ("email", email, "Email already registered"),
    ):
        owner = db.exec(select(User).where(getattr(User, field) == value)).first()
        if owner is not None and owner.id != exclude_id:
            return DuplicateResourceException(message, field=field)
    return None


class UserService:
    """Own user persistence and the rules governing privileged accounts."""

    def __init__(self, db: Session):
        self.db = db
        self.case_access = CaseAccess(db)

    @staticmethod
    def _require_human_account(user: User) -> None:
        if user.system_identity is not None:
            raise AuthorizationException(
                "Permanent AI system accounts cannot be modified"
            )

    def _persist_user(
        self,
        user: User,
        *,
        username_message: str,
        exclude_id: int | None = None,
        invalid_message: str = "Invalid user data",
    ) -> None:
        """Persist a user and translate a raced unique constraint at its source."""
        # Read before the write: a rollback expires the in-memory update.
        username, email = user.username, user.email
        try:
            with transaction(self.db):
                self.db.add(user)
                self.db.flush()
                if user.role == UserRole.ANALYST.value:
                    self.db.execute(
                        update(CaseUserLink)
                        .where(col(CaseUserLink.user_id) == user.id)
                        .values(is_lead=False)
                    )
        except IntegrityError as error:
            duplicate = duplicate_user_error(
                self.db, username, email, exclude_id, username_message
            )
            if duplicate:
                raise duplicate from error
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
                self._persist_user(
                    new_user, username_message="Username already registered"
                )
            setup.clear_setup_token()
            logger.bind(
                user_id=new_user.id,
                role=new_user.role,
                event_type="user_creation_success",
            ).info("Bootstrap administrator created successfully")
            return schemas.User.model_validate(new_user)
        except DomainException:
            raise
        except Exception as error:
            logger.bind(
                event_type="user_creation_error", error_type=type(error).__name__
            ).error("Bootstrap user creation failed unexpectedly")
            raise

    async def create_user_from_payload(
        self, user_data: object, current_user: User
    ) -> schemas.User:
        self.case_access.require_admin(current_user)
        user = _validate_user_payload(schemas.UserCreate, user_data)
        return await self.create_user(user, current_user)

    @audit_operation("user_creation")
    async def create_user(
        self, user: schemas.UserCreate, current_user: User
    ) -> schemas.User:
        self.case_access.require_admin(current_user)
        if user.is_superadmin and not current_user.is_superadmin:
            raise AuthorizationException("Only superadmin can create superadmin users")
        duplicate = duplicate_user_error(
            self.db,
            user.username,
            str(user.email),
            username_message="Username already registered",
        )
        if duplicate:
            raise duplicate

        new_user = self._new_user(user)
        self._persist_user(new_user, username_message="Username already registered")
        return schemas.User.model_validate(new_user)

    async def get_users(
        self, current_user: User, skip: int = 0, limit: int = 100
    ) -> list[schemas.User]:
        self.case_access.require_admin(current_user)
        users = self.db.exec(
            select(User).order_by(col(User.id)).offset(skip).limit(min(limit, 200))
        ).all()
        return [schemas.User.model_validate(user) for user in users]

    @audit_operation("user_update")
    async def update_user(
        self, user_id: int, user_update: schemas.UserUpdate, current_user: User
    ) -> schemas.User:
        is_admin = self.case_access.is_admin(current_user)
        if not is_admin and current_user.id != user_id:
            raise AuthorizationException("Not authorized")
        user = self.db.get(User, user_id)
        if user is None:
            raise ResourceNotFoundException("User not found")
        self._require_human_account(user)
        if user.is_superadmin and not current_user.is_superadmin:
            raise AuthorizationException("Only superadmin can edit superadmin users")
        updates = user_update.model_dump(exclude_unset=True)
        if current_user.id == user_id and not is_admin:
            updates.pop("role", None)
            if updates.pop("is_superadmin", None):
                raise AuthorizationException(
                    "Only superadmin can promote users to superadmin"
                )
        if updates.get("is_superadmin") and not current_user.is_superadmin:
            raise AuthorizationException(
                "Only superadmin can promote users to superadmin"
            )
        final_role = updates.get("role", user.role)
        if (
            user.role == UserRole.ADMIN.value
            and final_role != UserRole.ADMIN.value
            and not current_user.is_superadmin
        ):
            raise AuthorizationException("Only superadmin can demote admin users")
        final_superadmin = updates.get("is_superadmin", user.is_superadmin)
        if final_superadmin and final_role != UserRole.ADMIN.value:
            raise ValidationException("Only users with Admin role can be superadmin")
        duplicate = duplicate_user_error(
            self.db,
            updates.get("username", user.username),
            str(updates.get("email", user.email)),
            exclude_id=user_id,
        )
        if duplicate:
            raise duplicate
        updates["updated_at"] = get_utc_now()
        for field, value in updates.items():
            setattr(user, field, value)
        self._persist_user(
            user,
            exclude_id=user_id,
            username_message="Username already taken",
            invalid_message="Invalid update data",
        )
        return schemas.User.model_validate(user)

    @audit_operation("password_change")
    async def change_password(
        self, user_id: int, current_password: str, new_password: str, current_user: User
    ) -> schemas.User:
        user = self.db.get(User, user_id)
        if user is None:
            raise ResourceNotFoundException("User not found")
        self._require_human_account(user)
        if current_user.id != user_id:
            raise AuthorizationException("Not authorized")
        if not security.verify_password(current_password, user.password_hash):
            raise ValidationException("Invalid current password")
        self._replace_password(user, new_password, expected_hash=user.password_hash)
        return schemas.User.model_validate(user)

    @audit_operation("admin_password_reset")
    async def admin_reset_password(
        self, user_id: int, new_password: str, current_user: User
    ) -> schemas.User:
        self.case_access.require_admin(current_user)
        user = self.db.get(User, user_id)
        if user is None:
            raise ResourceNotFoundException("User not found")
        self._require_human_account(user)
        if user.is_superadmin and not current_user.is_superadmin:
            raise AuthorizationException(
                "Only superadmin can reset superadmin passwords"
            )
        self._replace_password(user, new_password)
        return schemas.User.model_validate(user)

    def _replace_password(
        self, user: User, new_password: str, *, expected_hash: str | None = None
    ) -> None:
        """Commit credentials and revocation together, without lost increments."""
        statement = update(User).where(
            col(User.id) == user.id, col(User.auth_identity) == user.auth_identity
        )
        if expected_hash is not None:
            statement = statement.where(col(User.password_hash) == expected_hash)
        with transaction(self.db):
            changed = self.db.execute(
                statement.values(
                    password_hash=security.get_password_hash(new_password),
                    session_version=col(User.session_version) + 1,
                    updated_at=get_utc_now(),
                ).returning(col(User.id)),
                execution_options={"synchronize_session": False},
            ).scalar_one_or_none()
            if changed is None:
                raise ValidationException("Password changed concurrently; try again")
            self.db.refresh(user)

    @audit_operation("user_deletion")
    async def delete_user(self, user_id: int, current_user: User) -> dict:
        self.case_access.require_admin(current_user)
        user = self.db.get(User, user_id)
        if user is None:
            raise ResourceNotFoundException("User not found")
        self._require_human_account(user)
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
