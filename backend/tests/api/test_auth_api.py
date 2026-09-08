"""Tests for authentication API endpoints."""

import asyncio
import threading

import bcrypt
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session

from app.core import security
from app.core.dependencies import get_current_user
from app.database.connection import get_db
from app.database.models import Case, Hunt, HuntExecution, User
from app.main import app


@pytest.fixture
def test_user_with_password(session: Session) -> tuple[User, str]:
    password = "testpassword123"
    user = User(
        username="testuser",
        email="testuser@example.com",
        password_hash=security.get_password_hash(password),
        is_active=True,
        role="Investigator",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user, password


def override_get_db_factory(session: Session):
    def override_get_db():
        return session

    return override_get_db


def test_setup_status_requires_setup_when_no_users_exist(
    session: Session, client: TestClient
):
    app.dependency_overrides[get_db] = override_get_db_factory(session)
    response = client.get("/api/auth/setup-status")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"setup_required": True}


def test_setup_status_is_complete_when_a_user_exists(
    session: Session, test_user_with_password: tuple[User, str], client: TestClient
):
    app.dependency_overrides[get_db] = override_get_db_factory(session)
    response = client.get("/api/auth/setup-status")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"setup_required": False}


def test_login_uses_persisted_password_hash(
    session: Session, test_user_with_password: tuple[User, str], client: TestClient
):
    user, password = test_user_with_password
    app.dependency_overrides[get_db] = override_get_db_factory(session)
    response = client.post(
        "/api/auth/login", data={"username": user.username, "password": password}
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


@pytest.mark.parametrize(
    ("username", "password"),
    [("nonexistent", "password123"), ("testuser", "wrongpassword"), ("", "")],
)
def test_login_rejects_invalid_credentials(
    session: Session,
    test_user_with_password: tuple[User, str],
    client: TestClient,
    username: str,
    password: str,
):
    app.dependency_overrides[get_db] = override_get_db_factory(session)
    response = client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Incorrect username or password"}


@pytest.mark.parametrize(
    "data", [{"username": "testuser"}, {"password": "password123"}]
)
def test_login_requires_both_form_fields(client: TestClient, data: dict[str, str]):
    response = client.post("/api/auth/login", data=data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.parametrize("account_state", ["active", "inactive", "missing"])
@pytest.mark.parametrize("password", ["a" * 73, "é" * 37, "a" * 200, "a" * 201])
def test_login_rejects_oversized_passwords_consistently(
    session: Session,
    test_user_with_password: tuple[User, str],
    client: TestClient,
    account_state: str,
    password: str,
):
    user, _ = test_user_with_password
    if account_state == "inactive":
        user.is_active = False
        session.add(user)
        session.commit()
    username = "missing" if account_state == "missing" else user.username
    response = client.post(
        "/api/auth/login", data={"username": username, "password": password}
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Incorrect username or password"}


@pytest.mark.asyncio
async def test_login_verification_allows_unrelated_api_work(
    session: Session, test_user_with_password: tuple[User, str], monkeypatch
):
    user, password = test_user_with_password
    started = threading.Event()
    release = threading.Event()
    event_loop_thread = threading.get_ident()
    checkpw = bcrypt.checkpw

    def held_checkpw(plain: bytes, hashed: bytes) -> bool:
        assert threading.get_ident() != event_loop_thread
        started.set()
        assert release.wait(10), "Verification was not released"
        return checkpw(plain, hashed)

    async def get_session():
        return session

    monkeypatch.setattr(bcrypt, "checkpw", held_checkpw)
    app.dependency_overrides[get_db] = get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as api:
        login = asyncio.create_task(
            api.post(
                "/api/auth/login",
                data={"username": user.username, "password": password},
            )
        )
        try:
            assert await asyncio.to_thread(started.wait, 3)
            health = await asyncio.wait_for(api.get("/health/live"), timeout=3)
            setup = await asyncio.wait_for(api.get("/api/auth/setup-status"), timeout=3)
            assert health.json() == {"status": "healthy"}
            assert setup.json() == {"setup_required": False}
            assert not login.done()
        finally:
            release.set()
            response = await login
        assert response.status_code == status.HTTP_200_OK
        profile = await api.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {response.json()['access_token']}"},
        )
        assert profile.status_code == status.HTTP_200_OK
        assert profile.json()["username"] == user.username


def _execution(session: Session, user: User) -> HuntExecution:
    case = Case(case_number="AUTH-API", title="Auth API case")
    hunt = Hunt(
        name="auth-api-hunt",
        display_name="Auth API hunt",
        description="fixture",
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
        created_by_id=user.id,
    )
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


@pytest.mark.parametrize(
    "execution_exists", [False, True], ids=["missing-is-404", "denied-is-403"]
)
def test_websocket_token_distinguishes_missing_from_denied_execution(
    session: Session,
    test_user_with_password: tuple[User, str],
    client: TestClient,
    execution_exists: bool,
):
    user, _ = test_user_with_password
    execution_id = _execution(session, user).id if execution_exists else 999_999

    async def current_user_override():
        return user

    app.dependency_overrides[get_db] = override_get_db_factory(session)
    app.dependency_overrides[get_current_user] = current_user_override
    response = client.post(
        "/api/auth/websocket-token", json={"execution_id": execution_id}
    )

    expected_status = (
        status.HTTP_403_FORBIDDEN if execution_exists else status.HTTP_404_NOT_FOUND
    )
    assert response.status_code == expected_status
