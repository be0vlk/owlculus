"""Public, session-backed tests for invitation workflows."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlmodel import Session, select

from app import schemas
from app.core.exceptions import (
    DuplicateResourceException,
    ResourceNotFoundException,
    ValidationException,
)
from app.core.security import verify_password
from app.core.utils import get_utc_now
from app.database import models
from app.services.invite_service import TOKEN_LENGTH, InviteService


def add_invite(
    session: Session,
    creator: models.User,
    *,
    token: str = "test-token",
    expires_in: timedelta = timedelta(hours=1),
    used: bool = False,
) -> models.Invite:
    invite = models.Invite(
        token=token,
        role="Investigator",
        expires_at=get_utc_now() + expires_in,
        used_at=get_utc_now() if used else None,
        created_by_id=creator.id,
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return invite


async def test_create_and_list_invites(session: Session, test_admin: models.User):
    service = InviteService(session)

    with patch(
        "app.services.invite_service.secrets.token_urlsafe",
        return_value="generated-token",
    ) as token_urlsafe:
        created = await service.create_invite(
            schemas.InviteCreate(role="Investigator"), current_user=test_admin
        )

    listed = await service.get_invites(current_user=test_admin)
    assert created.token == "generated-token"
    assert listed[0].id == created.id
    assert listed[0].created_by_username == test_admin.username
    token_urlsafe.assert_called_once_with(TOKEN_LENGTH)


@pytest.mark.parametrize(
    ("expires_in", "used", "error"),
    [
        (timedelta(hours=1), False, None),
        (timedelta(hours=-1), False, "Invite has expired"),
        (timedelta(hours=1), True, "Invite has already been used"),
    ],
)
async def test_validate_invite_states(
    session: Session,
    test_admin: models.User,
    expires_in: timedelta,
    used: bool,
    error: str | None,
):
    invite = add_invite(session, test_admin, expires_in=expires_in, used=used)

    result = await InviteService(session).validate_invite(invite.token)

    assert result.valid is (error is None)
    assert result.error == error


async def test_validate_unknown_invite(session: Session):
    result = await InviteService(session).validate_invite("missing")

    assert result.valid is False
    assert result.error == "Invalid invite token"


async def test_registration_creates_user_and_consumes_invite_atomically(
    session: Session, test_admin: models.User
):
    invite = add_invite(session, test_admin)
    service = InviteService(session)
    registration = schemas.UserRegistration(
        username="newuser",
        email="new@example.com",
        password="secret-password",
        token=invite.token,
    )

    with patch.object(session, "commit", wraps=session.commit) as commit:
        response = await service.register_user_with_invite(registration)

    persisted_user = session.exec(
        select(models.User).where(models.User.username == "newuser")
    ).one()
    session.refresh(invite)
    assert response.id == persisted_user.id
    assert verify_password("secret-password", persisted_user.password_hash)
    assert invite.used_at is not None
    commit.assert_called_once_with()


async def test_registration_rejects_duplicate_identity(
    session: Session, test_admin: models.User
):
    invite = add_invite(session, test_admin)
    registration = schemas.UserRegistration(
        username=test_admin.username,
        email="unused@example.com",
        password="secret-password",
        token=invite.token,
    )

    with pytest.raises(DuplicateResourceException) as error:
        await InviteService(session).register_user_with_invite(registration)

    assert error.value.field == "username"
    session.refresh(invite)
    assert invite.used_at is None


async def test_registration_rejects_invalid_invite(session: Session):
    registration = schemas.UserRegistration(
        username="newuser",
        email="new@example.com",
        password="secret-password",
        token="missing",
    )

    with pytest.raises(ValidationException, match="Invalid invite token"):
        await InviteService(session).register_user_with_invite(registration)


async def test_delete_invite(session: Session, test_admin: models.User):
    invite = add_invite(session, test_admin)
    service = InviteService(session)

    assert await service.delete_invite(invite.id, current_user=test_admin) is True
    assert session.get(models.Invite, invite.id) is None

    with pytest.raises(ResourceNotFoundException, match="Invite not found"):
        await service.delete_invite(invite.id, current_user=test_admin)


async def test_delete_used_invite_is_rejected(
    session: Session, test_admin: models.User
):
    invite = add_invite(session, test_admin, used=True)

    with pytest.raises(ValidationException, match="Cannot delete used invite"):
        await InviteService(session).delete_invite(invite.id, current_user=test_admin)


async def test_cleanup_deletes_only_unused_expired_invites(
    session: Session, test_admin: models.User
):
    expired = add_invite(
        session, test_admin, token="expired", expires_in=timedelta(hours=-1)
    )
    used = add_invite(
        session,
        test_admin,
        token="used",
        expires_in=timedelta(hours=-1),
        used=True,
    )
    active = add_invite(session, test_admin, token="active")

    count = await InviteService(session).cleanup_expired_invites(
        current_user=test_admin
    )

    assert count == 1
    assert session.get(models.Invite, expired.id) is None
    assert session.get(models.Invite, used.id) is not None
    assert session.get(models.Invite, active.id) is not None
