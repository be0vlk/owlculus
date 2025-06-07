"""
Comprehensive tests for system_config API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import status
from sqlmodel import Session
from unittest.mock import patch
from datetime import datetime, timezone

from app.main import app
from app.database.models import User, SystemConfiguration
from app.core.dependencies import get_current_user, get_db

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


@pytest.fixture
def test_system_config(session: Session) -> SystemConfiguration:
    config = SystemConfiguration(
        case_number_template="YYMM-NN", case_number_prefix=None
    )
    session.add(config)
    session.commit()
    session.refresh(config)
    return config


def override_get_db_factory(session: Session):
    def override_get_db():
        return session

    return override_get_db


def override_get_current_user_factory(user: User):
    def override_get_current_user():
        return user

    return override_get_current_user


class TestSystemConfigAPI:
    """Test cases for system_config API endpoints"""

    # GET /api/system_config/configuration tests

    def test_get_configuration_success_admin(
        self,
        session: Session,
        test_admin: User,
        test_system_config: SystemConfiguration,
    ):
        """Test successful configuration retrieval by admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.system_config_service.SystemConfigService.get_configuration"
            ) as mock_get:
                mock_get.return_value = test_system_config

                response = client.get("/api/admin/configuration")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["case_number_template"] == "YYMM-NN"
                assert data["case_number_prefix"] is None
                assert "id" in data
                assert "created_at" in data
                assert "updated_at" in data
        finally:
            app.dependency_overrides.clear()

    def test_get_configuration_creates_default(
        self, session: Session, test_admin: User
    ):
        """Test configuration retrieval creates default when none exists"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        default_config = SystemConfiguration(
            id=1,
            case_number_template="YYMM-NN",
            case_number_prefix=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        try:
            with patch(
                "app.services.system_config_service.SystemConfigService.get_configuration"
            ) as mock_get:
                mock_get.return_value = default_config

                response = client.get("/api/admin/configuration")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["case_number_template"] == "YYMM-NN"
        finally:
            app.dependency_overrides.clear()

    def test_get_configuration_forbidden_non_admin(
        self, session: Session, test_user: User
    ):
        """Test configuration retrieval forbidden for non-admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get("/api/admin/configuration")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_get_configuration_forbidden_analyst(
        self, session: Session, test_analyst: User
    ):
        """Test configuration retrieval forbidden for analyst"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_analyst
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get("/api/admin/configuration")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_get_configuration_unauthorized(self):
        """Test configuration retrieval without authentication"""
        response = client.get("/api/admin/configuration")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # PUT /api/system_config/configuration tests

    def test_update_configuration_success_yymm_template(
        self,
        session: Session,
        test_admin: User,
        test_system_config: SystemConfiguration,
    ):
        """Test successful configuration update with YYMM-NN template"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"case_number_template": "YYMM-NN", "case_number_prefix": None}

        updated_config = SystemConfiguration(**test_system_config.model_dump())
        updated_config.case_number_template = update_data["case_number_template"]
        updated_config.case_number_prefix = update_data["case_number_prefix"]

        try:
            with patch(
                "app.services.system_config_service.SystemConfigService.update_configuration"
            ) as mock_update:
                mock_update.return_value = updated_config

                response = client.put("/api/admin/configuration", json=update_data)
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["case_number_template"] == "YYMM-NN"
                assert data["case_number_prefix"] is None
        finally:
            app.dependency_overrides.clear()

    def test_update_configuration_success_prefix_template(
        self,
        session: Session,
        test_admin: User,
        test_system_config: SystemConfiguration,
    ):
        """Test successful configuration update with PREFIX-YYMM-NN template"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {
            "case_number_template": "PREFIX-YYMM-NN",
            "case_number_prefix": "CORP",
        }

        updated_config = SystemConfiguration(**test_system_config.model_dump())
        updated_config.case_number_template = update_data["case_number_template"]
        updated_config.case_number_prefix = update_data["case_number_prefix"]

        try:
            with patch(
                "app.services.system_config_service.SystemConfigService.update_configuration"
            ) as mock_update:
                mock_update.return_value = updated_config

                response = client.put("/api/admin/configuration", json=update_data)
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["case_number_template"] == "PREFIX-YYMM-NN"
                assert data["case_number_prefix"] == "CORP"
        finally:
            app.dependency_overrides.clear()

    def test_update_configuration_invalid_template(
        self, session: Session, test_admin: User
    ):
        """Test configuration update with invalid template"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {
            "case_number_template": "INVALID-TEMPLATE",
            "case_number_prefix": None,
        }

        try:
            # This will fail at Pydantic validation level
            response = client.put("/api/admin/configuration", json=update_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_update_configuration_missing_prefix_for_prefix_template(
        self, session: Session, test_admin: User
    ):
        """Test configuration update with PREFIX template but missing prefix"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {
            "case_number_template": "PREFIX-YYMM-NN",
            "case_number_prefix": None,
        }

        try:
            # This will fail at Pydantic validation level
            response = client.put("/api/admin/configuration", json=update_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_update_configuration_invalid_prefix(
        self, session: Session, test_admin: User
    ):
        """Test configuration update with invalid prefix"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {
            "case_number_template": "PREFIX-YYMM-NN",
            "case_number_prefix": "A",  # Too short
        }

        try:
            # This will fail at Pydantic validation level
            response = client.put("/api/admin/configuration", json=update_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_update_configuration_forbidden_non_admin(
        self, session: Session, test_user: User
    ):
        """Test configuration update forbidden for non-admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"case_number_template": "YYMM-NN", "case_number_prefix": None}

        try:
            response = client.put("/api/admin/configuration", json=update_data)
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_update_configuration_unauthorized(self):
        """Test configuration update without authentication"""
        update_data = {"case_number_template": "YYMM-NN", "case_number_prefix": None}

        response = client.put("/api/admin/configuration", json=update_data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_update_configuration_invalid_data_format(
        self, session: Session, test_admin: User
    ):
        """Test configuration update with invalid data format"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        # Missing required field
        update_data = {"case_number_prefix": "TEST"}

        try:
            response = client.put("/api/admin/configuration", json=update_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    # GET /api/system_config/configuration/preview tests

    def test_preview_configuration_success_yymm(
        self, session: Session, test_admin: User
    ):
        """Test successful configuration preview with YYMM-NN template"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.system_config_service.SystemConfigService.generate_example_case_number"
            ) as mock_generate:
                with patch(
                    "app.services.system_config_service.SystemConfigService.get_template_display_name"
                ) as mock_display:
                    mock_generate.return_value = "2506-01"
                    mock_display.return_value = "Monthly Reset (YYMM-NN)"

                    response = client.get(
                        "/api/admin/configuration/preview?template=YYMM-NN"
                    )
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["template"] == "YYMM-NN"
                    assert data["prefix"] is None
                    assert data["example_case_number"] == "2506-01"
                    assert data["display_name"] == "Monthly Reset (YYMM-NN)"
        finally:
            app.dependency_overrides.clear()

    def test_preview_configuration_success_prefix(
        self, session: Session, test_admin: User
    ):
        """Test successful configuration preview with PREFIX-YYMM-NN template"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.system_config_service.SystemConfigService.generate_example_case_number"
            ) as mock_generate:
                with patch(
                    "app.services.system_config_service.SystemConfigService.get_template_display_name"
                ) as mock_display:
                    mock_generate.return_value = "CORP-2506-01"
                    mock_display.return_value = (
                        "Prefix + Monthly Reset (PREFIX-YYMM-NN)"
                    )

                    response = client.get(
                        "/api/admin/configuration/preview?template=PREFIX-YYMM-NN&prefix=CORP"
                    )
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["template"] == "PREFIX-YYMM-NN"
                    assert data["prefix"] == "CORP"
                    assert data["example_case_number"] == "CORP-2506-01"
                    assert (
                        data["display_name"]
                        == "Prefix + Monthly Reset (PREFIX-YYMM-NN)"
                    )
        finally:
            app.dependency_overrides.clear()

    def test_preview_configuration_invalid_template(
        self, session: Session, test_admin: User
    ):
        """Test configuration preview with invalid template"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get(
                "/api/admin/configuration/preview?template=INVALID-TEMPLATE"
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            error_data = response.json()
            assert "Invalid template" in error_data["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_preview_configuration_missing_template(
        self, session: Session, test_admin: User
    ):
        """Test configuration preview without template parameter"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get("/api/admin/configuration/preview")
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_preview_configuration_forbidden_non_admin(
        self, session: Session, test_user: User
    ):
        """Test configuration preview forbidden for non-admin"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_user
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            response = client.get("/api/admin/configuration/preview?template=YYMM-NN")
            assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    def test_preview_configuration_unauthorized(self):
        """Test configuration preview without authentication"""
        response = client.get("/api/admin/configuration/preview?template=YYMM-NN")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # Edge cases and validation tests

    def test_configuration_api_special_characters_in_prefix(
        self, session: Session, test_admin: User
    ):
        """Test configuration with special characters in prefix"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {
            "case_number_template": "PREFIX-YYMM-NN",
            "case_number_prefix": "TEST@123",  # Special characters
        }

        try:
            # This will fail at Pydantic validation level
            response = client.put("/api/admin/configuration", json=update_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_configuration_api_prefix_too_long(
        self, session: Session, test_admin: User
    ):
        """Test configuration with prefix too long"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {
            "case_number_template": "PREFIX-YYMM-NN",
            "case_number_prefix": "VERYLONGPREFIX",  # Too long (more than 8 chars)
        }

        try:
            # This will fail at Pydantic validation level
            response = client.put("/api/admin/configuration", json=update_data)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        finally:
            app.dependency_overrides.clear()

    def test_configuration_api_case_insensitive_prefix(
        self,
        session: Session,
        test_admin: User,
        test_system_config: SystemConfiguration,
    ):
        """Test configuration with mixed case prefix"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {
            "case_number_template": "PREFIX-YYMM-NN",
            "case_number_prefix": "CoRp",  # Mixed case
        }

        updated_config = SystemConfiguration(**test_system_config.model_dump())
        updated_config.case_number_template = update_data["case_number_template"]
        updated_config.case_number_prefix = update_data["case_number_prefix"]

        try:
            with patch(
                "app.services.system_config_service.SystemConfigService.update_configuration"
            ) as mock_update:
                mock_update.return_value = updated_config

                response = client.put("/api/admin/configuration", json=update_data)
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["case_number_prefix"] == "CoRp"
        finally:
            app.dependency_overrides.clear()

    def test_configuration_api_null_values(
        self,
        session: Session,
        test_admin: User,
        test_system_config: SystemConfiguration,
    ):
        """Test configuration update with explicit null values"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"case_number_template": "YYMM-NN", "case_number_prefix": None}

        updated_config = SystemConfiguration(**test_system_config.model_dump())
        updated_config.case_number_template = update_data["case_number_template"]
        updated_config.case_number_prefix = None

        try:
            with patch(
                "app.services.system_config_service.SystemConfigService.update_configuration"
            ) as mock_update:
                mock_update.return_value = updated_config

                response = client.put("/api/admin/configuration", json=update_data)
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["case_number_prefix"] is None
        finally:
            app.dependency_overrides.clear()

    def test_configuration_api_response_format_consistency(
        self,
        session: Session,
        test_admin: User,
        test_system_config: SystemConfiguration,
    ):
        """Test consistent response format across endpoints"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.system_config_service.SystemConfigService.get_configuration"
            ) as mock_get:
                mock_get.return_value = test_system_config

                response = client.get("/api/admin/configuration")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()

                # Verify required fields are present
                required_fields = [
                    "id",
                    "case_number_template",
                    "case_number_prefix",
                    "created_at",
                    "updated_at",
                ]
                for field in required_fields:
                    assert field in data

                # Verify data types
                assert isinstance(data["id"], int)
                assert isinstance(data["case_number_template"], str)
                assert isinstance(data["created_at"], str)
                assert isinstance(data["updated_at"], str)
        finally:
            app.dependency_overrides.clear()

    def test_configuration_api_response_time(self, session: Session, test_admin: User):
        """Test API response time performance"""
        import time

        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        default_config = SystemConfiguration(
            id=1,
            case_number_template="YYMM-NN",
            case_number_prefix=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        try:
            with patch(
                "app.services.system_config_service.SystemConfigService.get_configuration"
            ) as mock_get:
                mock_get.return_value = default_config

                start_time = time.time()
                response = client.get("/api/admin/configuration")
                end_time = time.time()

                response_time = end_time - start_time

                assert response.status_code == status.HTTP_200_OK
                # Response should be reasonably fast (under 1 second for simple operations)
                assert response_time < 1.0
        finally:
            app.dependency_overrides.clear()

    def test_preview_configuration_empty_prefix(
        self, session: Session, test_admin: User
    ):
        """Test configuration preview with empty prefix parameter"""
        app.dependency_overrides[get_current_user] = override_get_current_user_factory(
            test_admin
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.system_config_service.SystemConfigService.generate_example_case_number"
            ) as mock_generate:
                with patch(
                    "app.services.system_config_service.SystemConfigService.get_template_display_name"
                ) as mock_display:
                    mock_generate.return_value = "2506-01"
                    mock_display.return_value = "Monthly Reset (YYMM-NN)"

                    response = client.get(
                        "/api/admin/configuration/preview?template=YYMM-NN&prefix="
                    )
                    assert response.status_code == status.HTTP_200_OK
                    data = response.json()
                    assert data["prefix"] == ""
        finally:
            app.dependency_overrides.clear()
