"""Isolated PostgreSQL regressions for multi-process invitation semantics.

Run with RUN_INVITE_POSTGRES=1. This verifies database serialization, not
exploitability of the default single-process API deployment.
"""

import asyncio
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine, select

from app import schemas
from app.core.exceptions import DuplicateResourceException, ValidationException
from app.core.utils import get_utc_now
from app.database import models
from app.services import invite_service
from app.services.invite_service import InviteService


@pytest.fixture(scope="module")
def postgres_engine():
    if os.environ.get("RUN_INVITE_POSTGRES") != "1":
        pytest.skip("Set RUN_INVITE_POSTGRES=1 for isolated Docker PostgreSQL tests")
    name = f"owlculus-invites-{uuid4().hex[:12]}"
    engine = None
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--pull=never",
                "--rm",
                "-d",
                "--name",
                name,
                "-p",
                "127.0.0.1::5432",
                "-e",
                "POSTGRES_PASSWORD=acceptance",
                "-e",
                "POSTGRES_DB=acceptance",
                "postgres:15-alpine",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        address = subprocess.check_output(
            ["docker", "port", name, "5432/tcp"], text=True
        ).strip()
        engine = create_engine(
            f"postgresql://postgres:acceptance@{address}/acceptance",
            connect_args={"options": "-c statement_timeout=10000"},
        )
        deadline = time.monotonic() + 30
        while True:
            try:
                with engine.connect():
                    break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
        SQLModel.metadata.create_all(engine)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, check=False)


@pytest.fixture
def invitation(postgres_engine):
    with Session(postgres_engine) as db:
        creator = models.User(
            username=uuid4().hex,
            email=f"{uuid4().hex}@example.com",
            password_hash="unused",
            role="Admin",
            is_superadmin=True,
        )
        db.add(creator)
        db.flush()
        invite = models.Invite(
            token=uuid4().hex,
            role="Admin",
            created_by_id=creator.id,
            expires_at=get_utc_now() + timedelta(hours=1),
        )
        db.add(invite)
        db.commit()
        return invite.token, creator.username


def registration(token, username=None):
    return schemas.UserRegistration(
        token=token,
        username=username or uuid4().hex,
        email=f"{uuid4().hex}@example.com",
        password="secret-password",
    )


def test_concurrent_redemption_has_one_committed_admin(postgres_engine, invitation):
    token, _ = invitation
    contenders = [registration(token), registration(token)]
    boundary = Barrier(2, timeout=10)
    connections = set()

    def contest(conn, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" in statement:
            connections.add(id(conn.connection.driver_connection))
            boundary.wait()

    def redeem(data):
        with Session(postgres_engine) as db:
            try:
                return asyncio.run(InviteService(db).register_user_with_invite(data))
            except ValidationException as error:
                return str(error)

    event.listen(postgres_engine, "before_cursor_execute", contest)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(redeem, contenders))
    finally:
        event.remove(postgres_engine, "before_cursor_execute", contest)

    assert len(connections) == 2
    winners = [value for value in outcomes if not isinstance(value, str)]
    assert len(winners) == 1
    assert "Invite has already been used" in outcomes
    with Session(postgres_engine) as db:
        accounts = db.exec(
            select(models.User).where(
                models.User.username.in_([data.username for data in contenders])
            )
        ).all()
        assert len(accounts) == 1
        assert accounts[0].id == winners[0].id
        assert accounts[0].role == "Admin"
        assert accounts[0].is_superadmin is False
        invites = db.exec(
            select(models.Invite).where(models.Invite.token == token)
        ).all()
        assert len(invites) == 1
        assert invites[0].used_at is not None


async def test_insert_failure_rolls_back_claim(
    postgres_engine, invitation, monkeypatch
):
    token, existing_username = invitation
    with Session(postgres_engine) as db:
        service = InviteService(db)
        original = service._registration_conflict
        calls = 0

        def concurrent_identity(data):
            nonlocal calls
            calls += 1
            return None if calls == 1 else original(data)

        monkeypatch.setattr(service, "_registration_conflict", concurrent_identity)
        with pytest.raises(DuplicateResourceException, match="Username already taken"):
            await service.register_user_with_invite(
                registration(token, existing_username)
            )
    with Session(postgres_engine) as db:
        invite = db.exec(
            select(models.Invite).where(models.Invite.token == token)
        ).one()
        assert invite.used_at is None
        winner = await InviteService(db).register_user_with_invite(registration(token))
        assert winner.role == "Admin"


@pytest.mark.parametrize(
    "change,error",
    [
        ("expire", "Invite has expired"),
        ("delete", "Invalid invite token"),
        ("use", "Invite has already been used"),
    ],
)
async def test_claim_rechecks_database_state(
    postgres_engine, invitation, monkeypatch, change, error
):
    token, _ = invitation
    data = registration(token)

    def change_after_validation(password):
        with Session(postgres_engine) as other:
            invite = other.exec(
                select(models.Invite).where(models.Invite.token == token)
            ).one()
            if change == "expire":
                invite.expires_at = get_utc_now() - timedelta(seconds=1)
            elif change == "delete":
                other.delete(invite)
            else:
                invite.used_at = get_utc_now()
            other.commit()
        return "unused"

    monkeypatch.setattr(invite_service, "get_password_hash", change_after_validation)
    with (
        Session(postgres_engine) as db,
        pytest.raises(ValidationException, match=error),
    ):
        await InviteService(db).register_user_with_invite(data)
    with Session(postgres_engine) as db:
        assert (
            db.exec(
                select(models.User).where(models.User.username == data.username)
            ).first()
            is None
        )


async def test_expiry_uses_clock_after_lock_acquisition(
    postgres_engine, invitation, monkeypatch
):
    token, _ = invitation
    data = registration(token)
    now = get_utc_now()
    clock = [now]
    monkeypatch.setattr(invite_service, "get_utc_now", lambda: clock[0])

    def advance_after_lock(conn, cursor, statement, parameters, context, executemany):
        if "FOR UPDATE" in statement:
            clock[0] = now + timedelta(hours=2)

    event.listen(postgres_engine, "after_cursor_execute", advance_after_lock)
    try:
        with (
            Session(postgres_engine) as db,
            pytest.raises(ValidationException, match="Invite has expired"),
        ):
            await InviteService(db).register_user_with_invite(data)
    finally:
        event.remove(postgres_engine, "after_cursor_execute", advance_after_lock)
    with Session(postgres_engine) as db:
        invite = db.exec(
            select(models.Invite).where(models.Invite.token == token)
        ).one()
        assert invite.used_at is None
        assert (
            db.exec(
                select(models.User).where(models.User.username == data.username)
            ).first()
            is None
        )
