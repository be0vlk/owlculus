"""
Tests for authentication API endpoints
"""

from unittest.mock import patch

import pytest
from app.core import security
from app.core.dependencies import get_db
from app.database import crud
from app.database.models import User
from app.main import app
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

client = TestClient(app)


@pytest.fixture
def test_user_with_password(session: Session) -> tuple[User, str]:
    """Create a test user and return both the user and the plain password"""
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


class TestAuthAPI:
    """Test cases for authentication API endpoints"""

    def test_login_success(self, session: Session, test_user_with_password: tuple[User, str]):
        """Test successful login"""
        user, password = test_user_with_password
        
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        try:
            # Mock crud.get_user_by_username to return our test user
            with patch("app.services.auth_service.crud.get_user_by_username") as mock_get_user:
                mock_get_user.return_value = user
                
                response = client.post(
                    "/api/auth/login",
                    data={
                        "username": user.username,
                        "password": password,
                    },
                )
                
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert "access_token" in data
                assert data["token_type"] == "bearer"
        finally:
            app.dependency_overrides.clear()

    def test_login_invalid_username(self, session: Session):
        """Test login with invalid username"""
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        try:
            # Mock crud.get_user_by_username to return None (user not found)
            with patch("app.services.auth_service.crud.get_user_by_username") as mock_get_user:
                mock_get_user.return_value = None
                
                response = client.post(
                    "/api/auth/login",
                    data={
                        "username": "nonexistent",
                        "password": "password123",
                    },
                )
                
                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Incorrect username or password" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_login_invalid_password(self, session: Session, test_user_with_password: tuple[User, str]):
        """Test login with invalid password"""
        user, _ = test_user_with_password
        
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        try:
            # Mock crud.get_user_by_username to return our test user
            with patch("app.services.auth_service.crud.get_user_by_username") as mock_get_user:
                mock_get_user.return_value = user
                
                # Password verification will fail naturally since we're providing wrong password
                response = client.post(
                    "/api/auth/login",
                    data={
                        "username": user.username,
                        "password": "wrongpassword",
                    },
                )
                
                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Incorrect username or password" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_login_missing_fields(self, session: Session):
        """Test login with missing fields"""
        # Missing password
        response = client.post(
            "/api/auth/login",
            data={
                "username": "testuser",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Missing username
        response = client.post(
            "/api/auth/login",
            data={
                "password": "password123",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_login_empty_credentials(self, session: Session):
        """Test login with empty credentials"""
        app.dependency_overrides[get_db] = override_get_db_factory(session)
        
        try:
            # Mock crud.get_user_by_username to return None for empty username
            with patch("app.services.auth_service.crud.get_user_by_username") as mock_get_user:
                mock_get_user.return_value = None
                
                response = client.post(
                    "/api/auth/login",
                    data={
                        "username": "",
                        "password": "",
                    },
                )
                
                assert response.status_code == status.HTTP_401_UNAUTHORIZED
                assert "Incorrect username or password" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()