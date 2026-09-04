"""Behaviour tests for the session-backed user module."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlmodel import Session, select

from app.core.exceptions import (
    AuthorizationException,
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.security import verify_password
from app.database.models import User
from app.schemas.user_schema import UserCreate, UserUpdate
from app.services.user_service import UserService


def user_payload(
    username: str = "created", email: str = "created@example.com", **changes
) -> UserCreate:
    values = {
        "username": username,
        "email": email,
        "password": "password123",
        "role": "Investigator",
        "is_active": True,
        "is_superadmin": False,
    }
    values.update(changes)
    return UserCreate(**values)


@pytest.mark.asyncio
async def test_create_user_persists_hashed_password(session: Session, test_admin: User):
    result = await UserService(session).create_user(user_payload(), test_admin)
    persisted = session.get(User, result.id)
    assert result.username == "created"
    assert persisted.password_hash != "password123"
    assert verify_password("password123", persisted.password_hash)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"), [("username", "admin"), ("email", "admin@test.com")]
)
async def test_create_user_names_duplicate_field(
    session: Session, test_admin: User, field: str, value: str
):
    payload = user_payload(**{field: value})
    with pytest.raises(DuplicateResourceException) as caught:
        await UserService(session).create_user(payload, test_admin)
    assert caught.value.field == field


def test_concurrent_creates_translate_integrity_error_with_real_transactions(engine):
    with Session(engine) as setup_session:
        admin = User(
            username="race-admin",
            email="race-admin@example.com",
            password_hash="hash",
            role="Admin",
            is_superadmin=True,
        )
        setup_session.add(admin)
        setup_session.commit()

    contenders_ready = Barrier(2)

    def create_contender():
        with Session(engine) as contender_session:
            contender_admin = contender_session.exec(
                select(User).where(User.username == "race-admin")
            ).one()
            contenders_ready.wait(timeout=5)
            try:
                return asyncio.run(
                    UserService(contender_session).create_user(
                        user_payload(username="raced-user", email="raced@example.com"),
                        contender_admin,
                    )
                )
            except DuplicateResourceException as error:
                return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: create_contender(), range(2)))

    duplicates = [
        outcome
        for outcome in outcomes
        if isinstance(outcome, DuplicateResourceException)
    ]
    assert len(duplicates) == 1
    assert duplicates[0].field == "username"
    with Session(engine) as verification_session:
        assert (
            len(
                verification_session.exec(
                    select(User).where(User.username == "raced-user")
                ).all()
            )
            == 1
        )


@pytest.mark.asyncio
async def test_non_admin_cannot_create_user(session: Session, test_user: User):
    with pytest.raises(AuthorizationException):
        await UserService(session).create_user(user_payload(), test_user)


@pytest.mark.asyncio
async def test_only_superadmin_can_create_superadmin(session: Session):
    admin = User(
        username="ordinary-admin",
        email="ordinary@example.com",
        password_hash="hash",
        role="Admin",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    with pytest.raises(AuthorizationException):
        await UserService(session).create_user(
            user_payload(role="Admin", is_superadmin=True), admin
        )


@pytest.mark.asyncio
async def test_superadmin_can_create_superadmin(session: Session, test_admin: User):
    result = await UserService(session).create_user(
        user_payload(role="Admin", is_superadmin=True), test_admin
    )
    assert result.is_superadmin is True


@pytest.mark.asyncio
async def test_admin_lists_users_with_limit_cap(session: Session, test_admin: User):
    for index in range(3):
        session.add(
            User(
                username=f"listed-{index}",
                email=f"listed-{index}@example.com",
                password_hash="hash",
            )
        )
    session.commit()
    result = await UserService(session).get_users(test_admin, skip=1, limit=500)
    assert len(result) == 3


@pytest.mark.asyncio
async def test_non_admin_cannot_list_users(session: Session, test_user: User):
    with pytest.raises(AuthorizationException):
        await UserService(session).get_users(test_user)


@pytest.mark.asyncio
async def test_user_cannot_promote_self(session: Session, test_user: User):
    with pytest.raises(AuthorizationException):
        await UserService(session).update_user(
            test_user.id,
            UserUpdate(username="renamed", role="Admin", is_superadmin=True),
            test_user,
        )


@pytest.mark.asyncio
async def test_user_cannot_update_someone_else(
    session: Session, test_user: User, test_analyst: User
):
    with pytest.raises(AuthorizationException):
        await UserService(session).update_user(
            test_analyst.id, UserUpdate(username="nope"), test_user
        )


@pytest.mark.asyncio
async def test_update_missing_user_is_not_found(session: Session, test_admin: User):
    with pytest.raises(ResourceNotFoundException):
        await UserService(session).update_user(
            999_999, UserUpdate(username="nope"), test_admin
        )


@pytest.mark.asyncio
async def test_update_names_duplicate_field(
    session: Session, test_admin: User, test_user: User
):
    with pytest.raises(DuplicateResourceException) as caught:
        await UserService(session).update_user(
            test_user.id, UserUpdate(email=test_admin.email), test_admin
        )
    assert caught.value.field == "email"


@pytest.mark.asyncio
async def test_update_advances_updated_at(
    session: Session, test_admin: User, test_user: User
):
    test_user.updated_at = test_user.updated_at.replace(year=2000)
    session.add(test_user)
    session.commit()
    previous_updated_at = test_user.updated_at
    result = await UserService(session).update_user(
        test_user.id, UserUpdate(username="updated-name"), test_admin
    )
    assert result.updated_at > previous_updated_at


@pytest.mark.asyncio
async def test_admin_cannot_edit_superadmin(session: Session, test_admin: User):
    ordinary_admin = User(
        username="ordinary-admin",
        email="ordinary@example.com",
        password_hash="hash",
        role="Admin",
    )
    session.add(ordinary_admin)
    session.commit()
    session.refresh(ordinary_admin)
    with pytest.raises(AuthorizationException):
        await UserService(session).update_user(
            test_admin.id, UserUpdate(username="nope"), ordinary_admin
        )


@pytest.mark.asyncio
async def test_change_password_checks_and_replaces_hash(
    session: Session, test_user: User
):
    await UserService(session).change_password(
        test_user.id, "userpass", "new-password", test_user
    )
    assert verify_password("new-password", test_user.password_hash)
    with pytest.raises(ValidationException):
        await UserService(session).change_password(
            test_user.id, "wrong", "another", test_user
        )


@pytest.mark.asyncio
async def test_admin_reset_obeys_superadmin_protection(
    session: Session, test_admin: User
):
    ordinary_admin = User(
        username="ordinary-admin",
        email="ordinary@example.com",
        password_hash="hash",
        role="Admin",
    )
    session.add(ordinary_admin)
    session.commit()
    session.refresh(ordinary_admin)
    with pytest.raises(AuthorizationException):
        await UserService(session).admin_reset_password(
            test_admin.id, "new-password", ordinary_admin
        )
    await UserService(session).admin_reset_password(
        ordinary_admin.id, "new-password", test_admin
    )
    assert verify_password("new-password", ordinary_admin.password_hash)


@pytest.mark.asyncio
async def test_delete_user_obeys_superadmin_and_admin_protections(
    session: Session, test_admin: User, test_user: User
):
    service = UserService(session)
    with pytest.raises(AuthorizationException):
        await service.delete_user(test_admin.id, test_admin)
    result = await service.delete_user(test_user.id, test_admin)
    assert result == {"message": "User 'user' deleted successfully"}
    assert session.exec(select(User).where(User.id == test_user.id)).first() is None
