"""
Comprehensive tests for users API endpoints
"""

from unittest.mock import patch

import pytest
from app.core.dependencies import get_current_user, get_db
from app.database.models import User
from app.main import app
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

client = TestClient(app)


@pytest.fixture
def test_admin(session: Session) -> User:
    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Admin",
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


@pytest.fixture
def test_user(session: Session) -> User:
    user = User(
        username="testuser",
        email="testuser@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Investigator",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def test_analyst(session: Session) -> User:
    analyst = User(
        username="analyst",
        email="analyst@example.com",
        password_hash="dummy_hash",
        is_active=True,
        role="Analyst",
    )
    session.add(analyst)
    session.commit()
    session.refresh(analyst)
    return analyst


def override_get_db_factory(session: Session):
    def override_get_db():
        return session

    return override_get_db


def override_get_current_user_factory(user: User):
    def override_get_current_user():
        return user

    return override_get_current_user


class TestUsersAPI:
    """Test cases for users API endpoints"""

    # POST /api/users/ tests

    def test_create_user_success_admin(self, session: Session, test_admin: User):
        """Test successful user creation by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "role": "Investigator",
            "is_active": True,
        }

        try:
            with patch(
                "app.services.user_service.UserService.create_user"
            ) as mock_create:
                mock_user = User(
                    id=1,
                    username=user_data["username"],
                    email=user_data["email"],
                    password_hash="hashed_password",
                    role=user_data["role"],
                    is_active=user_data["is_active"],
                )
                mock_create.return_value = mock_user

                response = client.post("/api/users/", json=user_data)
                assert response.status_code == status.HTTP_201_CREATED
                data = response.json()
                assert data["username"] == user_data["username"]
                assert data["email"] == user_data["email"]
                assert data["role"] == user_data["role"]
        finally:
            app.dependency_overrides.clear()

    def test_create_user_forbidden_non_admin(self, session: Session, test_user: User):
        """Test user creation forbidden for non-admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "role": "Investigator",
            "is_active": True,
        }

        try:
            with patch(
                "app.services.user_service.UserService.create_user"
            ) as mock_create:
                from fastapi import HTTPException

                mock_create.side_effect = HTTPException(
                    status_code=403, detail="Permission denied"
                )

                response = client.post("/api/users/", json=user_data)
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_create_user_invalid_data(self, session: Session, test_admin: User):
        """Test user creation with invalid data"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        # Missing required fields
        user_data = {"username": "newuser"}

        try:
            response = client.post("/api/users/", json=user_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_create_user_duplicate_username(self, session: Session, test_admin: User):
        """Test user creation with duplicate username"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        user_data = {
            "username": "admin",  # Duplicate username
            "email": "newadmin@example.com",
            "password": "password123",
            "role": "Admin",
            "is_active": True,
        }

        try:
            with patch(
                "app.services.user_service.UserService.create_user"
            ) as mock_create:
                from fastapi import HTTPException

                mock_create.side_effect = HTTPException(
                    status_code=400, detail="Username already registered"
                )

                response = client.post("/api/users/", json=user_data)
                assert response.status_code == status.HTTP_400_BAD_REQUEST
        finally:
            app.dependency_overrides.clear()

    # GET /api/users/me tests

    def test_read_self_success(self, session: Session, test_user: User):
        """Test successful self profile retrieval"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )

        try:
            response = client.get("/api/users/me")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == test_user.id
            assert data["username"] == test_user.username
            assert data["email"] == test_user.email
        finally:
            app.dependency_overrides.clear()

    def test_read_self_unauthorized(self):
        """Test self profile retrieval without authentication"""
        response = client.get("/api/users/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # GET /api/users/ tests

    def test_get_users_success_admin(
        self, session: Session, test_admin: User, test_user: User
    ):
        """Test successful users listing by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch("app.services.user_service.UserService.get_users") as mock_get:
                mock_get.return_value = [test_admin, test_user]

                response = client.get("/api/users/")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert len(data) == 2
                assert any(user["username"] == "admin" for user in data)
                assert any(user["username"] == "testuser" for user in data)
        finally:
            app.dependency_overrides.clear()

    def test_get_users_with_pagination(self, session: Session, test_admin: User):
        """Test users listing with pagination"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch("app.services.user_service.UserService.get_users") as mock_get:
                mock_get.return_value = []

                response = client.get("/api/users/?skip=10&limit=5")
                assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()

    def test_get_users_forbidden_non_admin(self, session: Session, test_user: User):
        """Test users listing forbidden for non-admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch("app.services.user_service.UserService.get_users") as mock_get:
                from fastapi import HTTPException

                mock_get.side_effect = HTTPException(
                    status_code=403, detail="Permission denied"
                )

                response = client.get("/api/users/")
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    # PUT /api/users/{user_id} tests

    def test_update_user_success_admin(
        self, session: Session, test_admin: User, test_user: User
    ):
        """Test successful user update by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {
            "username": "updateduser",
            "email": "updated@example.com",
            "role": "Admin",
        }

        try:
            with patch(
                "app.services.user_service.UserService.update_user"
            ) as mock_update:
                updated_user = User(**test_user.model_dump())
                updated_user.username = update_data["username"]
                updated_user.email = update_data["email"]
                updated_user.role = update_data["role"]
                mock_update.return_value = updated_user

                response = client.put(f"/api/users/{test_user.id}", json=update_data)
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["username"] == update_data["username"]
                assert data["email"] == update_data["email"]
                assert data["role"] == update_data["role"]
        finally:
            app.dependency_overrides.clear()

    def test_update_user_self(self, session: Session, test_user: User):
        """Test user updating their own profile"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"username": "updatedself", "email": "updatedself@example.com"}

        try:
            with patch(
                "app.services.user_service.UserService.update_user"
            ) as mock_update:
                updated_user = User(**test_user.model_dump())
                updated_user.username = update_data["username"]
                updated_user.email = update_data["email"]
                mock_update.return_value = updated_user

                response = client.put(f"/api/users/{test_user.id}", json=update_data)
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["username"] == update_data["username"]
        finally:
            app.dependency_overrides.clear()

    def test_update_user_not_found(self, session: Session, test_admin: User):
        """Test user update with non-existent ID"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"username": "nonexistent"}

        try:
            with patch(
                "app.services.user_service.UserService.update_user"
            ) as mock_update:
                from fastapi import HTTPException

                mock_update.side_effect = HTTPException(
                    status_code=404, detail="User not found"
                )

                response = client.put("/api/users/999", json=update_data)
                assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    def test_update_user_forbidden_other_user(
        self, session: Session, test_user: User, test_analyst: User
    ):
        """Test user update forbidden for other users"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"username": "hacker"}

        try:
            with patch(
                "app.services.user_service.UserService.update_user"
            ) as mock_update:
                from fastapi import HTTPException

                mock_update.side_effect = HTTPException(
                    status_code=403, detail="Permission denied"
                )

                response = client.put(f"/api/users/{test_analyst.id}", json=update_data)
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    # PUT /api/users/me/password tests

    def test_change_password_success(self, session: Session, test_user: User):
        """Test successful password change"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {
            "current_password": "oldpassword",
            "new_password": "newpassword123",
        }

        try:
            with patch(
                "app.services.user_service.UserService.change_password"
            ) as mock_change:
                mock_change.return_value = test_user

                response = client.put("/api/users/me/password", json=password_data)
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["id"] == test_user.id
        finally:
            app.dependency_overrides.clear()

    def test_change_password_wrong_current(self, session: Session, test_user: User):
        """Test password change with wrong current password"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newpassword123",
        }

        try:
            with patch(
                "app.services.user_service.UserService.change_password"
            ) as mock_change:
                from fastapi import HTTPException

                mock_change.side_effect = HTTPException(
                    status_code=400, detail="Current password is incorrect"
                )

                response = client.put("/api/users/me/password", json=password_data)
                assert response.status_code == status.HTTP_400_BAD_REQUEST
        finally:
            app.dependency_overrides.clear()

    def test_change_password_weak_password(self, session: Session, test_user: User):
        """Test password change with weak password"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {
            "current_password": "oldpassword",
            "new_password": "123",  # Weak password
        }

        try:
            with patch(
                "app.services.user_service.UserService.change_password"
            ) as mock_change:
                from fastapi import HTTPException

                mock_change.side_effect = HTTPException(
                    status_code=400, detail="Password too weak"
                )

                response = client.put("/api/users/me/password", json=password_data)
                assert response.status_code == status.HTTP_400_BAD_REQUEST
        finally:
            app.dependency_overrides.clear()

    # PUT /api/users/{user_id}/password tests

    def test_admin_reset_password_success(
        self, session: Session, test_admin: User, test_user: User
    ):
        """Test successful admin password reset"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {"new_password": "resetpassword123"}

        try:
            with patch(
                "app.services.user_service.UserService.admin_reset_password"
            ) as mock_reset:
                mock_reset.return_value = test_user

                response = client.put(
                    f"/api/users/{test_user.id}/password", json=password_data
                )
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["id"] == test_user.id
        finally:
            app.dependency_overrides.clear()

    def test_admin_reset_password_forbidden_non_admin(
        self, session: Session, test_user: User, test_analyst: User
    ):
        """Test admin password reset forbidden for non-admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {"new_password": "resetpassword123"}

        try:
            with patch(
                "app.services.user_service.UserService.admin_reset_password"
            ) as mock_reset:
                from fastapi import HTTPException

                mock_reset.side_effect = HTTPException(
                    status_code=403, detail="Permission denied"
                )

                response = client.put(
                    f"/api/users/{test_analyst.id}/password", json=password_data
                )
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_admin_reset_password_user_not_found(
        self, session: Session, test_admin: User
    ):
        """Test admin password reset with non-existent user"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        password_data = {"new_password": "resetpassword123"}

        try:
            with patch(
                "app.services.user_service.UserService.admin_reset_password"
            ) as mock_reset:
                from fastapi import HTTPException

                mock_reset.side_effect = HTTPException(
                    status_code=404, detail="User not found"
                )

                response = client.put("/api/users/999/password", json=password_data)
                assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    # Authentication and authorization tests

    def test_users_api_unauthorized(self):
        """Test users API endpoints without authentication"""
        endpoints = [
            (
                "POST",
                "/api/users/",
                {
                    "username": "test",
                    "email": "test@example.com",
                    "password": "pass",
                    "role": "Analyst",
                    "is_active": True,
                },
            ),
            ("GET", "/api/users/"),
            ("PUT", "/api/users/1", {"username": "updated"}),
            (
                "PUT",
                "/api/users/me/password",
                {"current_password": "old", "new_password": "new"},
            ),
            ("PUT", "/api/users/1/password", {"new_password": "new"}),
        ]

        for method, endpoint, *data in endpoints:
            json_data = data[0] if data else {}

            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json=json_data)
            elif method == "PUT":
                response = client.put(endpoint, json=json_data)

            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # Edge cases and validation tests

    def test_users_api_pagination_edge_cases(self, session: Session, test_admin: User):
        """Test pagination with edge case values"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch("app.services.user_service.UserService.get_users") as mock_get:
                mock_get.return_value = []

                # Test with very large values
                response = client.get("/api/users/?skip=999999&limit=999999")
                assert response.status_code == status.HTTP_200_OK

                # Test with zero limit
                response = client.get("/api/users/?skip=0&limit=0")
                assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()

    def test_users_api_invalid_role(self, session: Session, test_admin: User):
        """Test user creation with invalid role"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
            "role": "InvalidRole",  # Invalid role
            "is_active": True,
        }

        try:
            response = client.post("/api/users/", json=user_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_users_api_invalid_email_format(self, session: Session, test_admin: User):
        """Test user creation with invalid email format"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        user_data = {
            "username": "newuser",
            "email": "invalid-email",  # Invalid email format
            "password": "password123",
            "role": "Analyst",
            "is_active": True,
        }

        try:
            response = client.post("/api/users/", json=user_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_users_api_error_format_consistency(
        self, session: Session, test_admin: User
    ):
        """Test consistent error response format"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.user_service.UserService.update_user"
            ) as mock_update:
                from fastapi import HTTPException

                mock_update.side_effect = HTTPException(
                    status_code=404, detail="User not found"
                )

                response = client.put("/api/users/999", json={"username": "test"})
                assert response.status_code == status.HTTP_404_NOT_FOUND
                error_data = response.json()
                assert "detail" in error_data
                assert isinstance(error_data["detail"], str)
        finally:
            app.dependency_overrides.clear()

    def test_users_api_response_time(self, session: Session, test_admin: User):
        """Test API response time performance"""
        import time

        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch("app.services.user_service.UserService.get_users") as mock_get:
                mock_get.return_value = []

                start_time = time.time()
                response = client.get("/api/users/")
                end_time = time.time()

                response_time = end_time - start_time

                assert response.status_code == status.HTTP_200_OK
                # Response should be reasonably fast (under 1 second for simple operations)
                assert response_time < 1.0
        finally:
            app.dependency_overrides.clear()
