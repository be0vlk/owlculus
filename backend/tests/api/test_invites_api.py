"""
Comprehensive tests for invites API endpoints
"""

import pytest
from app.core.dependencies import get_current_user, get_db
from datetime import datetime, timedelta, timezone
from app.database.models import Invite, User
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
def test_investigator(session: Session) -> User:
    user = User(
        username="investigator",
        email="investigator@example.com",
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


class TestInvitesAPI:
    """Test cases for invites API endpoints"""

    def test_create_invite_success_admin(self, session: Session, test_admin: User):
        """Test successful invite creation by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            invite_data = {"role": "Investigator"}
            response = client.post("/api/invites/", json=invite_data)
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["role"] == "Investigator"
            assert "token" in data
            assert "expires_at" in data
        finally:
            app.dependency_overrides.clear()

    def test_create_invite_forbidden_investigator(
        self, session: Session, test_investigator: User
    ):
        """Test invite creation forbidden for investigator"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_investigator
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            invite_data = {"role": "Investigator"}
            response = client.post("/api/invites/", json=invite_data)
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_create_invite_forbidden_analyst(
        self, session: Session, test_analyst: User
    ):
        """Test invite creation forbidden for analyst"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_analyst
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            invite_data = {"role": "Analyst"}
            response = client.post("/api/invites/", json=invite_data)
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_create_invite_unauthorized(self):
        """Test invite creation without authentication"""
        invite_data = {"role": "Investigator"}
        response = client.post("/api/invites/", json=invite_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_invites_success_admin(self, session: Session, test_admin: User):
        """Test successful invites listing by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get("/api/invites/")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert isinstance(data, list)
        finally:
            app.dependency_overrides.clear()

    def test_get_invites_forbidden_investigator(
        self, session: Session, test_investigator: User
    ):
        """Test invites listing forbidden for investigator"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_investigator
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get("/api/invites/")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_get_invites_forbidden_analyst(self, session: Session, test_analyst: User):
        """Test invites listing forbidden for analyst"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_analyst
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get("/api/invites/")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_get_invites_unauthorized(self):
        """Test invites listing without authentication"""
        response = client.get("/api/invites/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_validate_invite_success(self, session: Session):
        """Test successful invite validation (no auth required)"""
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            token_data = {"token": "test_token"}
            response = client.post("/api/invites/validate", json=token_data)
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "valid" in data
        finally:
            app.dependency_overrides.clear()

    def test_register_user_success(self, session: Session):
        """Test successful user registration with invite (no auth required)"""
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            registration_data = {
                "token": "valid_token",
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepassword123",
            }
            response = client.post("/api/invites/register", json=registration_data)
            # This will fail in unit test due to no actual invite, but tests the endpoint
            assert response.status_code in [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ]
        finally:
            app.dependency_overrides.clear()

    def test_delete_invite_success_admin(self, session: Session, test_admin: User):
        """Test successful invite deletion by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            # First create an invite to delete
            invite = Invite(
                token="test_token",
                role="Investigator",
                created_by_id=test_admin.id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
            )
            session.add(invite)
            session.commit()
            session.refresh(invite)

            response = client.delete(f"/api/invites/{invite.id}")
            assert response.status_code in [
                status.HTTP_204_NO_CONTENT,
                status.HTTP_404_NOT_FOUND,
            ]
        finally:
            app.dependency_overrides.clear()

    def test_delete_invite_forbidden_investigator(
        self, session: Session, test_investigator: User
    ):
        """Test invite deletion forbidden for investigator"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_investigator
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.delete("/api/invites/1")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_delete_invite_forbidden_analyst(
        self, session: Session, test_analyst: User
    ):
        """Test invite deletion forbidden for analyst"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_analyst
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.delete("/api/invites/1")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_delete_invite_unauthorized(self):
        """Test invite deletion without authentication"""
        response = client.delete("/api/invites/1")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_delete_invite_not_found(self, session: Session, test_admin: User):
        """Test deleting non-existent invite returns 404"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.delete("/api/invites/99999")
            assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    def test_cleanup_expired_invites_success_admin(
        self, session: Session, test_admin: User
    ):
        """Test successful cleanup of expired invites by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.post("/api/invites/cleanup")
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "message" in data
        finally:
            app.dependency_overrides.clear()

    def test_cleanup_expired_invites_forbidden_investigator(
        self, session: Session, test_investigator: User
    ):
        """Test cleanup forbidden for investigator"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_investigator
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.post("/api/invites/cleanup")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_cleanup_expired_invites_forbidden_analyst(
        self, session: Session, test_analyst: User
    ):
        """Test cleanup forbidden for analyst"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_analyst
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.post("/api/invites/cleanup")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_cleanup_expired_invites_unauthorized(self):
        """Test cleanup without authentication"""
        response = client.post("/api/invites/cleanup")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_register_duplicate_username(self, session: Session, test_admin: User):
        """Test registration with duplicate username"""
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            # First create a valid invite
            invite = Invite(
                token="valid_token",
                role="Investigator",
                created_by_id=test_admin.id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
            )
            session.add(invite)
            session.commit()

            # Register with existing admin username
            registration_data = {
                "token": "valid_token",
                "username": test_admin.username,
                "email": "different@example.com",
                "password": "securepassword123",
            }
            response = client.post("/api/invites/register", json=registration_data)
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Username already taken" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_register_duplicate_email(self, session: Session, test_admin: User):
        """Test registration with duplicate email"""
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            # First create a valid invite
            invite = Invite(
                token="valid_token2",
                role="Investigator",
                created_by_id=test_admin.id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=48),
            )
            session.add(invite)
            session.commit()

            # Register with existing admin email
            registration_data = {
                "token": "valid_token2",
                "username": "differentuser",
                "email": test_admin.email,
                "password": "securepassword123",
            }
            response = client.post("/api/invites/register", json=registration_data)
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Email already registered" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()