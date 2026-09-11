"""Behaviour tests for the session-backed authentication module."""

import asyncio
import threading

import bcrypt
import pytest
from anyio import wait_all_tasks_blocked
from sqlmodel import Session

from app.core import security
from app.core.exceptions import (
    AuthenticationException,
    AuthorizationException,
    ResourceNotFoundException,
)
from app.database.models import Case, CaseUserLink, Hunt, HuntExecution, User
from app.schemas.auth_schema import Token, WebSocketToken
from app.services.auth_service import AuthService


@pytest.mark.asyncio
async def test_authenticate_returns_token_schema_with_real_password_hash(
    session: Session, test_user: User
):
    result = await AuthService(session).authenticate_user("user", "userpass")
    assert isinstance(result, Token)
    assert result.token_type == "bearer"
    assert result.access_token


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("missing", "userpass"),
        ("user", "wrong"),
        ("", "userpass"),
        ("user", ""),
        ("u" * 101, "userpass"),
        ("user", "p" * 200),
        ("user", "p" * 201),
    ],
)
async def test_authenticate_rejects_invalid_credentials(
    session: Session, test_user: User, username: str, password: str
):
    with pytest.raises(AuthenticationException, match="Incorrect username or password"):
        await AuthService(session).authenticate_user(username, password)


@pytest.mark.asyncio
async def test_authenticate_rejects_inactive_account(
    session: Session, test_inactive_user: User
):
    with pytest.raises(AuthenticationException, match="Incorrect username or password"):
        await AuthService(session).authenticate_user("inactive", "inactivepass")


@pytest.mark.asyncio
@pytest.mark.parametrize("password", ["a" * 72, "é" * 36])
async def test_authenticate_accepts_bcrypt_byte_boundary_without_truncation(
    session: Session, test_user: User, password: str
):
    test_user.username = "u" * 100
    test_user.password_hash = security.get_password_hash(password)
    session.add(test_user)
    session.commit()
    result = await AuthService(session).authenticate_user(test_user.username, password)
    assert security.verify_access_token(
        result.access_token, AuthenticationException()
    ) == (
        test_user.auth_identity,
        test_user.session_version,
    )
    # Exercise the installed bcrypt implementation, not a fake length check.
    with pytest.raises(ValueError, match="72 bytes"):
        security.verify_password(password + "a", test_user.password_hash)
    with pytest.raises(AuthenticationException, match="Incorrect username or password"):
        await AuthService(session).authenticate_user(test_user.username, password + "a")


@pytest.mark.asyncio
async def test_login_password_execution_capacity_is_bounded(
    session: Session, test_user: User, monkeypatch
):
    release = threading.Event()
    saturated = threading.Event()
    lock = threading.Lock()
    entered = 0

    def held_checkpw(plain: bytes, hashed: bytes) -> bool:
        nonlocal entered
        with lock:
            entered += 1
            if entered == 4:
                saturated.set()
        assert release.wait(10), "Verification was not released"
        return False

    monkeypatch.setattr(bcrypt, "checkpw", held_checkpw)
    logins = [
        asyncio.create_task(AuthService(session).authenticate_user("user", "wrong"))
        for _ in range(5)
    ]
    try:
        assert await asyncio.to_thread(saturated.wait, 3)
        await wait_all_tasks_blocked()
        with lock:
            assert entered == 4
        assert all(not login.done() for login in logins)
    finally:
        release.set()
        results = await asyncio.gather(*logins, return_exceptions=True)
    assert all(isinstance(result, AuthenticationException) for result in results)
    assert entered == 5


def _execution(session: Session, creator: User) -> HuntExecution:
    case = Case(case_number="AUTH-001", title="Auth case")
    hunt = Hunt(
        name="auth-hunt",
        display_name="Auth hunt",
        description="Authentication fixture",
        category="test",
        definition_json={},
    )
    session.add(case)
    session.add(hunt)
    session.commit()
    session.refresh(case)
    session.refresh(hunt)
    execution = HuntExecution(
        hunt_id=hunt.id,
        case_id=case.id,
        initial_parameters={},
        created_by_id=creator.id,
    )
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


@pytest.mark.asyncio
async def test_websocket_token_returns_schema_for_readable_execution(
    session: Session, test_user: User, monkeypatch
):
    from unittest.mock import MagicMock

    from redis import Redis

    # Redis transport is exercised across real processes in test_observation.
    monkeypatch.setattr(Redis, "from_url", MagicMock())
    execution = _execution(session, test_user)
    session.add(CaseUserLink(case_id=execution.case_id, user_id=test_user.id))
    session.commit()
    result = await AuthService(session).create_websocket_token(execution.id, test_user)
    assert isinstance(result, WebSocketToken)
    assert result.execution_id == execution.id
    assert result.expires_in == 30
    assert result.token


@pytest.mark.asyncio
async def test_websocket_token_reports_missing_execution_before_access(
    session: Session, test_user: User
):
    with pytest.raises(ResourceNotFoundException, match="Execution not found"):
        await AuthService(session).create_websocket_token(999_999, test_user)


@pytest.mark.asyncio
async def test_websocket_token_rejects_existing_inaccessible_case(
    session: Session, test_user: User
):
    execution = _execution(session, test_user)
    with pytest.raises(AuthorizationException):
        await AuthService(session).create_websocket_token(execution.id, test_user)


def test_handshake_logs_redact_observation_tokens(caplog):
    import logging

    from app.core.logging import ObservationTokenFilter

    logger = logging.getLogger("observation-handshake-test")
    redaction = ObservationTokenFilter()
    logger.addFilter(redaction)
    try:
        with caplog.at_level(logging.INFO, logger=logger.name):
            logger.info(
                "WebSocket %s accepted",
                "/api/hunts/executions/1/stream?token=private-capability&cursor=1-0",
            )
            logger.info(
                "WebSocket /api/plugins/executions/1/stream?token=another-capability accepted"
            )
        assert "private-capability" not in caplog.text
        assert "another-capability" not in caplog.text
        assert "[redacted]&cursor=1-0" in caplog.text
    finally:
        logger.removeFilter(redaction)
