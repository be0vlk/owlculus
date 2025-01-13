import pytest
from sqlmodel import Session, SQLModel, create_engine
from fastapi.testclient import TestClient
from fastapi.security import OAuth2PasswordBearer
from datetime import timedelta
from fastapi import HTTPException
from app.database import crud

from app.main import app
from app.database import models
from app.core.security import (
    get_password_hash,
    create_access_token,
    verify_access_token,
)
from app.core.config import settings
from app.core.dependencies import get_current_user, get_current_active_user

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(name="session")
def session_fixture(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(name="client")
def client_fixture(session):
    def get_session_override():
        return session

    app.dependency_overrides[Session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="test_admin")
def test_admin_fixture(session):
    admin_user = models.User(
        email="admin@test.com",
        username="admin",
        password_hash=get_password_hash("adminpass"),
        role="Admin",
        is_active=True,
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)
    return admin_user


@pytest.fixture(name="test_user")
def test_user_fixture(session):
    user = models.User(
        email="user@test.com",
        username="user",
        password_hash=get_password_hash("userpass"),
        role="User",
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="test_analyst")
def test_analyst_fixture(session):
    analyst = models.User(
        email="analyst@test.com",
        username="analyst",
        password_hash=get_password_hash("analystpass"),
        role="Analyst",
        is_active=True,
    )
    session.add(analyst)
    session.commit()
    session.refresh(analyst)
    return analyst


@pytest.fixture(name="admin_token")
def admin_token_fixture(test_admin):
    access_token = create_access_token(
        data={"sub": test_admin.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return access_token


@pytest.fixture(name="user_token")
def user_token_fixture(test_user):
    access_token = create_access_token(
        data={"sub": test_user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return access_token


@pytest.fixture(name="analyst_token")
def analyst_token_fixture(test_analyst):
    access_token = create_access_token(
        data={"sub": test_analyst.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return access_token


@pytest.fixture(name="override_auth")
def override_auth_fixture(session):
    """Override authentication dependencies for testing"""

    async def mock_get_current_user(token: str = None):
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            username = verify_access_token(token, HTTPException(status_code=401))
            user = await crud.get_user_by_username(session, username=username)
            if not user:
                raise HTTPException(status_code=401)
            return user
        except:
            raise HTTPException(status_code=401)

    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_current_active_user] = mock_get_current_user
    yield
    app.dependency_overrides.clear()
