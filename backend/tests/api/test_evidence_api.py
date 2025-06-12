"""
Comprehensive tests for evidence API endpoints
"""

from unittest.mock import patch

import pytest
from app.core.dependencies import get_current_active_user, get_db
from app.database.models import Case, CaseUserLink, Client, Evidence, User
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


@pytest.fixture
def test_client_data(session: Session) -> Client:
    test_client = Client(name="Test Client", email="client@example.com")
    session.add(test_client)
    session.commit()
    session.refresh(test_client)
    return test_client


@pytest.fixture
def test_case(session: Session, test_client_data: Client, test_admin: User) -> Case:
    case = Case(
        client_id=test_client_data.id,
        case_number="TEST-001",
        title="Test Case",
        status="Open",
    )
    session.add(case)
    session.commit()
    session.refresh(case)

    # Link admin to case
    case_user_link = CaseUserLink(case_id=case.id, user_id=test_admin.id)
    session.add(case_user_link)
    session.commit()
    return case


@pytest.fixture
def test_evidence(session: Session, test_case: Case, test_admin: User) -> Evidence:
    evidence = Evidence(
        case_id=test_case.id,
        title="Test Evidence",
        description="Test description",
        evidence_type="file",
        category="Document",
        content="test file content",
        folder_path="/test/path/file.txt",
        created_by_id=test_admin.id,
    )
    session.add(evidence)
    session.commit()
    session.refresh(evidence)
    return evidence


@pytest.fixture
def test_folder(session: Session, test_case: Case, test_admin: User) -> Evidence:
    folder = Evidence(
        case_id=test_case.id,
        title="Test Folder",
        description="Test folder description",
        evidence_type="folder",
        category="Folder",
        content="",
        is_folder=True,
        created_by_id=test_admin.id,
    )
    session.add(folder)
    session.commit()
    session.refresh(folder)
    return folder


def override_get_db_factory(session: Session):
    def override_get_db():
        return session

    return override_get_db


def override_get_current_user_factory(user: User):
    def override_get_current_user():
        return user

    return override_get_current_user


class TestEvidenceAPI:
    """Test cases for evidence API endpoints"""

    # GET /api/evidence/case/{case_id} tests

    def test_get_case_evidence_success(
        self,
        session: Session,
        test_admin: User,
        test_case: Case,
        test_evidence: Evidence,
    ):
        """Test successful case evidence listing"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.get_case_evidence"
            ) as mock_get:
                mock_get.return_value = [test_evidence]

                response = client.get(f"/api/evidence/case/{test_case.id}")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert len(data) == 1
                assert data[0]["title"] == test_evidence.title
        finally:
            app.dependency_overrides.clear()

    def test_get_case_evidence_with_pagination(
        self, session: Session, test_admin: User, test_case: Case
    ):
        """Test case evidence listing with pagination"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.get_case_evidence"
            ) as mock_get:
                mock_get.return_value = []

                response = client.get(
                    f"/api/evidence/case/{test_case.id}?skip=10&limit=5"
                )
                assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()

    def test_get_case_evidence_forbidden_non_assigned(
        self, session: Session, test_user: User, test_case: Case
    ):
        """Test case evidence listing forbidden for non-assigned user"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_user)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.get_case_evidence"
            ) as mock_get:
                from fastapi import HTTPException

                mock_get.side_effect = HTTPException(
                    status_code=403, detail="Not authorized"
                )

                response = client.get(f"/api/evidence/case/{test_case.id}")
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    # GET /api/evidence/{evidence_id} tests

    def test_get_evidence_success(
        self, session: Session, test_admin: User, test_evidence: Evidence
    ):
        """Test successful evidence retrieval"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.get_evidence"
            ) as mock_get:
                mock_get.return_value = test_evidence

                response = client.get(f"/api/evidence/{test_evidence.id}")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["id"] == test_evidence.id
                assert data["title"] == test_evidence.title
        finally:
            app.dependency_overrides.clear()

    def test_get_evidence_not_found(self, session: Session, test_admin: User):
        """Test evidence retrieval with non-existent ID"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.get_evidence"
            ) as mock_get:
                from fastapi import HTTPException

                mock_get.side_effect = HTTPException(
                    status_code=404, detail="Evidence not found"
                )

                response = client.get("/api/evidence/999")
                assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    # GET /api/evidence/{evidence_id}/download tests

    def test_download_evidence_success(
        self, session: Session, test_admin: User, test_evidence: Evidence
    ):
        """Test successful evidence download"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.download_evidence"
            ) as mock_download:
                # Create a simple response instead of FileResponse which requires real file
                from fastapi.responses import Response

                mock_response = Response(
                    content=b"test file content", media_type="application/octet-stream"
                )
                mock_download.return_value = mock_response

                response = client.get(f"/api/evidence/{test_evidence.id}/download")
                assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()

    def test_download_evidence_not_found(self, session: Session, test_admin: User):
        """Test evidence download with non-existent ID"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.download_evidence"
            ) as mock_download:
                from fastapi import HTTPException

                mock_download.side_effect = HTTPException(
                    status_code=404, detail="Evidence not found"
                )

                response = client.get("/api/evidence/999/download")
                assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    # PUT /api/evidence/{evidence_id} tests

    def test_update_evidence_success(
        self, session: Session, test_admin: User, test_evidence: Evidence
    ):
        """Test successful evidence update"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {
            "title": "Updated Evidence",
            "description": "Updated description",
        }

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.update_evidence"
            ) as mock_update:
                updated_evidence = Evidence(**test_evidence.model_dump())
                updated_evidence.title = update_data["title"]
                updated_evidence.description = update_data["description"]
                mock_update.return_value = updated_evidence

                response = client.put(
                    f"/api/evidence/{test_evidence.id}", json=update_data
                )
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["title"] == update_data["title"]
                assert data["description"] == update_data["description"]
        finally:
            app.dependency_overrides.clear()

    def test_update_evidence_not_found(self, session: Session, test_admin: User):
        """Test evidence update with non-existent ID"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"title": "Updated Evidence"}

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.update_evidence"
            ) as mock_update:
                from fastapi import HTTPException

                mock_update.side_effect = HTTPException(
                    status_code=404, detail="Evidence not found"
                )

                response = client.put("/api/evidence/999", json=update_data)
                assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    def test_update_evidence_forbidden_analyst(
        self, session: Session, test_analyst: User, test_evidence: Evidence
    ):
        """Test evidence update forbidden for analyst"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_analyst)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"title": "Updated Evidence"}

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.update_evidence"
            ) as mock_update:
                from fastapi import HTTPException

                mock_update.side_effect = HTTPException(
                    status_code=403, detail="Permission denied"
                )

                response = client.put(
                    f"/api/evidence/{test_evidence.id}", json=update_data
                )
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    # DELETE /api/evidence/{evidence_id} tests

    def test_delete_evidence_success(
        self, session: Session, test_admin: User, test_evidence: Evidence
    ):
        """Test successful evidence deletion"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.delete_evidence"
            ) as mock_delete:
                mock_delete.return_value = test_evidence

                response = client.delete(f"/api/evidence/{test_evidence.id}")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["id"] == test_evidence.id
        finally:
            app.dependency_overrides.clear()

    def test_delete_evidence_not_found(self, session: Session, test_admin: User):
        """Test evidence deletion with non-existent ID"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.delete_evidence"
            ) as mock_delete:
                from fastapi import HTTPException

                mock_delete.side_effect = HTTPException(
                    status_code=404, detail="Evidence not found"
                )

                response = client.delete("/api/evidence/999")
                assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()

    def test_delete_evidence_forbidden_analyst(
        self, session: Session, test_analyst: User, test_evidence: Evidence
    ):
        """Test evidence deletion forbidden for analyst"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_analyst)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.delete_evidence"
            ) as mock_delete:
                from fastapi import HTTPException

                mock_delete.side_effect = HTTPException(
                    status_code=403, detail="Permission denied"
                )

                response = client.delete(f"/api/evidence/{test_evidence.id}")
                assert response.status_code == status.HTTP_403_FORBIDDEN
        finally:
            app.dependency_overrides.clear()

    # Folder management tests

    def test_create_folder_success(
        self, session: Session, test_admin: User, test_case: Case
    ):
        """Test successful folder creation"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        folder_data = {
            "case_id": test_case.id,
            "title": "New Folder",
            "description": "Test folder",
        }

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.create_folder"
            ) as mock_create:
                mock_folder = Evidence(
                    id=1,
                    title="New Folder",
                    case_id=test_case.id,
                    evidence_type="folder",
                    category="Folder",
                    content="",
                    is_folder=True,
                    created_by_id=test_admin.id,
                )
                mock_create.return_value = mock_folder

                response = client.post("/api/evidence/folders", json=folder_data)
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["title"] == folder_data["title"]
                assert data["evidence_type"] == "folder"
        finally:
            app.dependency_overrides.clear()

    def test_get_folder_tree_success(
        self, session: Session, test_admin: User, test_case: Case, test_folder: Evidence
    ):
        """Test successful folder tree retrieval"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.get_folder_tree"
            ) as mock_get:
                mock_get.return_value = [test_folder]

                response = client.get(f"/api/evidence/case/{test_case.id}/folder-tree")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert len(data) == 1
                assert data[0]["evidence_type"] == "folder"
        finally:
            app.dependency_overrides.clear()

    def test_update_folder_success(
        self, session: Session, test_admin: User, test_folder: Evidence
    ):
        """Test successful folder update"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        update_data = {"name": "Updated Folder", "description": "Updated description"}

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.update_folder"
            ) as mock_update:
                updated_folder = Evidence(**test_folder.model_dump())
                updated_folder.title = update_data["name"]
                updated_folder.description = update_data["description"]
                mock_update.return_value = updated_folder

                response = client.put(
                    f"/api/evidence/folders/{test_folder.id}", json=update_data
                )
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["title"] == update_data["name"]
        finally:
            app.dependency_overrides.clear()

    def test_delete_folder_success(
        self, session: Session, test_admin: User, test_folder: Evidence
    ):
        """Test successful folder deletion"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.delete_folder"
            ) as mock_delete:
                mock_delete.return_value = test_folder

                response = client.delete(f"/api/evidence/folders/{test_folder.id}")
                assert response.status_code == status.HTTP_200_OK
                data = response.json()
                assert data["id"] == test_folder.id
        finally:
            app.dependency_overrides.clear()

    # Authentication and authorization tests

    def test_evidence_api_unauthorized(self):
        """Test evidence API endpoints without authentication"""
        # Test various endpoints without auth
        endpoints = [
            ("GET", "/api/evidence/case/1"),
            ("GET", "/api/evidence/1"),
            ("GET", "/api/evidence/1/download"),
            ("PUT", "/api/evidence/1"),
            ("DELETE", "/api/evidence/1"),
            ("POST", "/api/evidence/folders"),
            ("GET", "/api/evidence/case/1/folder-tree"),
            ("PUT", "/api/evidence/folders/1"),
            ("DELETE", "/api/evidence/folders/1"),
        ]

        for method, endpoint in endpoints:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})
            elif method == "PUT":
                response = client.put(endpoint, json={})
            elif method == "DELETE":
                response = client.delete(endpoint)

            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # Edge cases and validation tests

    def test_evidence_api_pagination_edge_cases(
        self, session: Session, test_admin: User, test_case: Case
    ):
        """Test pagination with edge case values"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.get_case_evidence"
            ) as mock_get:
                mock_get.return_value = []

                # Test with very large values
                response = client.get(
                    f"/api/evidence/case/{test_case.id}?skip=999999&limit=999999"
                )
                assert response.status_code == status.HTTP_200_OK

                # Test with zero limit
                response = client.get(
                    f"/api/evidence/case/{test_case.id}?skip=0&limit=0"
                )
                assert response.status_code == status.HTTP_200_OK

        finally:
            app.dependency_overrides.clear()

    def test_evidence_api_invalid_case_id(self, session: Session, test_admin: User):
        """Test evidence endpoints with invalid case ID"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.get_case_evidence"
            ) as mock_get:
                from fastapi import HTTPException

                mock_get.side_effect = HTTPException(
                    status_code=404, detail="Case not found"
                )

                response = client.get("/api/evidence/case/999")
                assert response.status_code == status.HTTP_404_NOT_FOUND

        finally:
            app.dependency_overrides.clear()

    def test_evidence_api_error_format_consistency(
        self, session: Session, test_admin: User
    ):
        """Test consistent error response format"""
        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.get_evidence"
            ) as mock_get:
                from fastapi import HTTPException

                mock_get.side_effect = HTTPException(
                    status_code=404, detail="Evidence not found"
                )

                response = client.get("/api/evidence/999")
                assert response.status_code == status.HTTP_404_NOT_FOUND
                error_data = response.json()
                assert "detail" in error_data
                assert isinstance(error_data["detail"], str)

        finally:
            app.dependency_overrides.clear()

    def test_evidence_api_response_time(
        self, session: Session, test_admin: User, test_case: Case
    ):
        """Test API response time performance"""
        import time

        app.dependency_overrides[get_current_active_user] = (
            override_get_current_user_factory(test_admin)
        )
        app.dependency_overrides[get_db] = override_get_db_factory(session)

        try:
            with patch(
                "app.services.evidence_service.EvidenceService.get_case_evidence"
            ) as mock_get:
                mock_get.return_value = []

                start_time = time.time()
                response = client.get(f"/api/evidence/case/{test_case.id}")
                end_time = time.time()

                response_time = end_time - start_time

                assert response.status_code == status.HTTP_200_OK
                # Response should be reasonably fast (under 1 second for simple operations)
                assert response_time < 1.0

        finally:
            app.dependency_overrides.clear()
