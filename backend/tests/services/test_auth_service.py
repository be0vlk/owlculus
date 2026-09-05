"""Behaviour tests for the session-backed authentication module."""

import pytest
from sqlmodel import Session

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
    [("missing", "userpass"), ("user", "wrong"), ("", "userpass")],
)
async def test_authenticate_rejects_invalid_credentials(
    session: Session, test_user: User, username: str, password: str
):
    with pytest.raises(AuthenticationException, match="Incorrect username or password"):
        await AuthService(session).authenticate_user(username, password)


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
