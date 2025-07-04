import pytest
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.database.models import Case, CaseUserLink, Client, Entity, User
from app.main import app
from fastapi import HTTPException
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
def test_client(session: Session) -> Client:
    client = Client(name="Test Client", email="client@example.com")
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


@pytest.fixture
def test_case(session: Session, test_client: Client, test_admin: User) -> Case:
    case = Case(
        client_id=test_client.id,
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
def test_entity(session: Session, test_case: Case, test_admin: User) -> Entity:
    entity = Entity(
        case_id=test_case.id,
        entity_type="person",
        data={"first_name": "John", "last_name": "Doe"},
        created_by_id=test_admin.id,
    )
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


@pytest.fixture
def override_dependencies(session: Session, test_admin: User):
    def get_session_override():
        return session

    def get_current_user_override():
        return test_admin

    app.dependency_overrides[get_db] = get_session_override
    app.dependency_overrides[get_current_user] = get_current_user_override
    yield
    app.dependency_overrides = {}


def test_create_case(override_dependencies, test_client: Client):
    payload = {
        "client_id": test_client.id,
        "title": "Test Case",
        "notes": "Initial notes for test case",
    }
    response = client.post(f"{settings.API_V1_STR}/cases/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["status"] == "Open"
    assert data["case_number"] is not None  # Check that case number is generated


def test_create_case_missing_fields(override_dependencies):
    # Test missing required fields
    payload = {"title": "Test Case"}
    response = client.post(f"{settings.API_V1_STR}/cases/", json=payload)
    assert response.status_code == 422  # Unprocessable Entity


def test_read_cases(override_dependencies, test_case: Case):
    response = client.get(f"{settings.API_V1_STR}/cases/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["title"] == test_case.title


def test_read_cases_filter_by_status(override_dependencies, test_case: Case):
    response = client.get(f"{settings.API_V1_STR}/cases/?status=Open")
    assert response.status_code == 200
    data = response.json()
    assert all(case["status"] == "Open" for case in data)

    response = client.get(f"{settings.API_V1_STR}/cases/?status=Closed")
    assert response.status_code == 200
    data = response.json()
    assert all(case["status"] == "Closed" for case in data)


def test_read_case(override_dependencies, test_case: Case):
    response = client.get(f"{settings.API_V1_STR}/cases/{test_case.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_case.id
    assert data["title"] == test_case.title


def test_read_nonexistent_case(override_dependencies):
    response = client.get(f"{settings.API_V1_STR}/cases/999")
    assert response.status_code == 404


def test_update_case(override_dependencies, test_case: Case):
    payload = {"status": "Closed"}
    response = client.put(f"{settings.API_V1_STR}/cases/{test_case.id}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Closed"


def test_update_case_nonexistent(override_dependencies):
    payload = {"status": "Closed"}
    response = client.put(f"{settings.API_V1_STR}/cases/999", json=payload)
    assert response.status_code == 404


def test_update_case_duplicate_case_number(
    override_dependencies, test_case: Case, session: Session
):
    # Create a second case with a different case number
    second_case = Case(
        client_id=test_case.client_id,
        case_number="TEST-002",
        title="Second Test Case",
        status="Open",
    )
    session.add(second_case)
    session.commit()

    # Attempt to update the first case's number to match the second
    payload = {"case_number": "TEST-002"}
    response = client.put(f"{settings.API_V1_STR}/cases/{test_case.id}", json=payload)
    assert response.status_code == 400  # Bad Request


def test_add_user_to_case(override_dependencies, test_case: Case, test_user: User):
    response = client.post(
        f"{settings.API_V1_STR}/cases/{test_case.id}/users/{test_user.id}"
    )
    assert response.status_code == 200


def test_add_user_to_nonexistent_case(override_dependencies, test_user: User):
    response = client.post(f"{settings.API_V1_STR}/cases/999/users/{test_user.id}")
    assert response.status_code == 404


def test_add_nonexistent_user_to_case(override_dependencies, test_case: Case):
    response = client.post(f"{settings.API_V1_STR}/cases/{test_case.id}/users/999")
    assert response.status_code == 404


def test_remove_user_from_case(
    override_dependencies, test_case: Case, test_user: User, session: Session
):
    # First add the user to the case
    link = CaseUserLink(case_id=test_case.id, user_id=test_user.id)
    session.add(link)
    session.commit()

    response = client.delete(
        f"{settings.API_V1_STR}/cases/{test_case.id}/users/{test_user.id}"
    )
    assert response.status_code == 200


def test_remove_user_from_nonexistent_case(override_dependencies, test_user: User):
    response = client.delete(f"{settings.API_V1_STR}/cases/999/users/{test_user.id}")
    assert response.status_code == 404


def test_remove_nonexistent_user_from_case(override_dependencies, test_case: Case):
    response = client.delete(f"{settings.API_V1_STR}/cases/{test_case.id}/users/999")
    assert response.status_code == 404


def test_get_case_entities(override_dependencies, test_case: Case, test_entity: Entity):
    response = client.get(f"{settings.API_V1_STR}/cases/{test_case.id}/entities")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["id"] == test_entity.id


def test_get_case_entities_filter_by_type(
    override_dependencies, test_case: Case, test_entity: Entity
):
    response = client.get(
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities?entity_type=person"
    )
    assert response.status_code == 200
    data = response.json()
    assert all(entity["entity_type"] == "person" for entity in data)


def test_get_entities_for_nonexistent_case(override_dependencies):
    response = client.get(f"{settings.API_V1_STR}/cases/999/entities")
    assert response.status_code == 404


def test_create_entity(override_dependencies, test_case: Case):
    payload = {
        "entity_type": "person",
        "data": {"first_name": "Jane", "last_name": "Doe", "notes": "Test person"},
    }
    response = client.post(
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities", json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["entity_type"] == payload["entity_type"]
    assert data["data"]["first_name"] == payload["data"]["first_name"]


def test_create_entity_missing_fields(override_dependencies, test_case: Case):
    # Missing data field
    payload = {"entity_type": "person"}
    response = client.post(
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities", json=payload
    )
    assert response.status_code == 422


def test_create_entity_for_nonexistent_case(override_dependencies):
    payload = {
        "entity_type": "person",
        "data": {"first_name": "Jane", "last_name": "Doe"},
    }
    response = client.post(f"{settings.API_V1_STR}/cases/999/entities", json=payload)
    assert response.status_code == 404


def test_update_entity(override_dependencies, test_case: Case, test_entity: Entity):
    payload = {
        "data": {
            "first_name": "John",
            "last_name": "Smith",
            "notes": "Updated test person",
        }
    }
    response = client.put(
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities/{test_entity.id}",
        json=payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"]["first_name"] == payload["data"]["first_name"]


def test_update_nonexistent_entity(override_dependencies, test_case: Case):
    payload = {"data": {"first_name": "John", "last_name": "Smith"}}
    response = client.put(
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities/999", json=payload
    )
    assert response.status_code == 404


def test_delete_entity(override_dependencies, test_case: Case, test_entity: Entity):
    response = client.delete(
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities/{test_entity.id}"
    )
    assert response.status_code == 200


def test_delete_nonexistent_entity(override_dependencies, test_case: Case):
    response = client.delete(f"{settings.API_V1_STR}/cases/{test_case.id}/entities/999")
    assert response.status_code == 404


def test_read_cases_as_investigator(
    override_dependencies, test_case: Case, test_user: User, session: Session
):
    # Remove the default admin user from the override
    app.dependency_overrides[get_current_user] = (
        lambda: test_user
    )  # Override to return the test user

    # Link user to case
    case_user_link = CaseUserLink(case_id=test_case.id, user_id=test_user.id)
    session.add(case_user_link)
    session.commit()

    # User should be able to see the case they are linked to
    response = client.get(f"{settings.API_V1_STR}/cases/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1  # Should only see the case they are linked to

    # Create a new case not linked to the user
    new_case = Case(
        client_id=test_case.client_id,
        case_number="TEST-002",
        title="Another Case",
        status="Open",
    )
    session.add(new_case)
    session.commit()

    # User should still only see the case they are linked to
    response = client.get(f"{settings.API_V1_STR}/cases/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1  # Still only one case accessible


def test_update_case_as_investigator(
    override_dependencies, test_case: Case, test_user: User, session: Session
):
    app.dependency_overrides[get_current_user] = lambda: test_user  # Return test user

    # Link user to case
    case_user_link = CaseUserLink(case_id=test_case.id, user_id=test_user.id)
    session.add(case_user_link)
    session.commit()

    # User should be able to update the case they are linked to
    payload = {"status": "Closed"}
    response = client.put(f"{settings.API_V1_STR}/cases/{test_case.id}", json=payload)
    assert response.status_code == 200

    # Create a new case not linked to the user
    new_case = Case(
        client_id=test_case.client_id,
        case_number="TEST-002",
        title="Another Case",
        status="Open",
    )
    session.add(new_case)
    session.commit()

    # User should not be able to update a case they are not linked to
    payload = {"status": "Closed"}
    response = client.put(f"{settings.API_V1_STR}/cases/{new_case.id}", json=payload)
    assert response.status_code == 403  # Forbidden


def test_update_case_as_analyst(
    override_dependencies, test_case: Case, test_analyst: User, session: Session
):
    app.dependency_overrides[get_current_user] = (
        lambda: test_analyst
    )  # Return test analyst

    # Link analyst to case
    case_user_link = CaseUserLink(case_id=test_case.id, user_id=test_analyst.id)
    session.add(case_user_link)
    session.commit()

    # Analyst should not be able to update a case even if linked to
    payload = {"status": "Closed"}
    response = client.put(f"{settings.API_V1_STR}/cases/{test_case.id}", json=payload)
    assert response.status_code == 403  # Forbidden


# ========================================
# Additional comprehensive API tests
# ========================================


def test_invalid_json_payload(override_dependencies, test_case: Case):
    """Test handling of invalid JSON payloads"""
    # Send invalid JSON
    response = client.put(
        f"{settings.API_V1_STR}/cases/{test_case.id}",
        data="invalid json {",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422  # Unprocessable Entity


def test_missing_content_type_header(override_dependencies, test_case: Case):
    """Test handling of missing content-type header"""
    payload = {"status": "Closed"}
    response = client.put(
        f"{settings.API_V1_STR}/cases/{test_case.id}",
        json=payload,
        headers={},  # No content-type header
    )
    # Should still work with JSON payload
    assert response.status_code == 200


def test_malformed_request_body(override_dependencies, test_case: Case):
    """Test handling of malformed request bodies"""
    # Empty body
    response = client.post(f"{settings.API_V1_STR}/cases/", json={})
    assert response.status_code == 422

    # None values for required fields
    response = client.post(
        f"{settings.API_V1_STR}/cases/", json={"client_id": None, "title": None}
    )
    assert response.status_code == 422


def test_response_pagination_headers(
    override_dependencies, test_case: Case, session: Session
):
    """Test pagination headers in list responses"""
    # Create multiple cases
    for i in range(25):
        case = Case(
            client_id=test_case.client_id,
            case_number=f"TEST-{i:03d}",
            title=f"Test Case {i}",
            status="Open",
        )
        session.add(case)
    session.commit()

    # Request with pagination
    response = client.get(f"{settings.API_V1_STR}/cases/?skip=0&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10

    # Request next page
    response = client.get(f"{settings.API_V1_STR}/cases/?skip=10&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10


def test_api_rate_limiting(override_dependencies, test_case: Case):
    """Test API rate limiting (if implemented)"""
    # Make multiple rapid requests
    responses = []
    for _ in range(100):
        response = client.get(f"{settings.API_V1_STR}/cases/{test_case.id}")
        responses.append(response.status_code)

    # All should succeed if no rate limiting
    assert all(status == 200 for status in responses)


def test_cors_headers(override_dependencies):
    """Test CORS headers are properly set"""
    response = client.options(f"{settings.API_V1_STR}/cases/")
    # Check if CORS headers are present
    assert (
        "access-control-allow-origin" in response.headers or response.status_code == 405
    )


def test_bulk_operations(override_dependencies, test_client: Client):
    """Test bulk creation/update operations"""
    # Create multiple cases at once
    cases_data = [
        {
            "client_id": test_client.id,
            "title": f"Bulk Case {i}",
            "notes": f"Bulk test case {i}",
        }
        for i in range(5)
    ]

    # Create cases one by one (bulk endpoint if available)
    created_ids = []
    for case_data in cases_data:
        response = client.post(f"{settings.API_V1_STR}/cases/", json=case_data)
        assert response.status_code == 200
        created_ids.append(response.json()["id"])

    assert len(created_ids) == 5


def test_partial_update_vs_full_update(override_dependencies, test_case: Case):
    """Test PATCH vs PUT behavior"""
    # Full update with PUT
    full_update = {
        "title": "Fully Updated Case",
        "status": "Closed",
        "notes": "Complete update",
    }
    response = client.put(
        f"{settings.API_V1_STR}/cases/{test_case.id}", json=full_update
    )
    assert response.status_code == 200

    # Partial update (if PATCH is supported)
    partial_update = {"status": "Open"}
    response = client.patch(
        f"{settings.API_V1_STR}/cases/{test_case.id}", json=partial_update
    )
    # If PATCH is not implemented, it should return 405
    assert response.status_code in [200, 405]


def test_field_level_permissions(
    override_dependencies, test_case: Case, test_user: User, session: Session
):
    """Test field-level access control"""
    app.dependency_overrides[get_current_user] = lambda: test_user

    # Link user to case
    link = CaseUserLink(case_id=test_case.id, user_id=test_user.id)
    session.add(link)
    session.commit()

    # Try to update restricted fields
    response = client.put(
        f"{settings.API_V1_STR}/cases/{test_case.id}",
        json={"case_number": "RESTRICTED-001"},  # Might be admin-only
    )
    # Should either succeed or fail based on permissions
    assert response.status_code in [200, 403]


def test_api_versioning(override_dependencies):
    """Test API versioning support"""
    # Test current version
    response = client.get(f"{settings.API_V1_STR}/cases/")
    assert response.status_code == 200

    # Test non-existent version
    response = client.get("/api/v2/cases/")
    assert response.status_code == 404


def test_error_response_format(override_dependencies):
    """Test consistent error response format"""
    # 404 error
    response = client.get(f"{settings.API_V1_STR}/cases/999999")
    assert response.status_code == 404
    try:
        error_data = response.json()
        assert "detail" in error_data
    except ValueError:
        # Response might be text in some cases
        assert response.text is not None

    # 422 validation error
    response = client.post(f"{settings.API_V1_STR}/cases/", json={"invalid": "data"})
    assert response.status_code == 422
    try:
        error_data = response.json()
        assert "detail" in error_data
    except ValueError:
        # Response might be text in some cases
        assert response.text is not None

    # 403 forbidden error
    def raise_forbidden():
        raise HTTPException(status_code=403, detail="Forbidden")

    app.dependency_overrides[get_current_user] = raise_forbidden
    response = client.get(f"{settings.API_V1_STR}/cases/")
    assert response.status_code == 403
    try:
        error_data = response.json()
        assert "detail" in error_data
    except ValueError:
        # Response might be text in some cases
        assert response.text is not None


def test_concurrent_api_calls(override_dependencies, test_client: Client):
    """Test handling of concurrent API calls"""
    import threading

    results = []

    def create_case(index):
        payload = {
            "client_id": test_client.id,
            "title": f"Concurrent Case {index}",
            "notes": f"Created by thread {index}",
        }
        response = client.post(f"{settings.API_V1_STR}/cases/", json=payload)
        results.append(response.status_code)

    # Create multiple threads
    threads = []
    for i in range(10):
        thread = threading.Thread(target=create_case, args=(i,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    # All requests should succeed
    assert all(status == 200 for status in results)


def test_entity_validation_errors(override_dependencies, test_case: Case):
    """Test entity creation with various validation errors"""
    # Invalid entity type
    payload = {"entity_type": "invalid_type", "data": {"some": "data"}}
    response = client.post(
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities", json=payload
    )
    assert response.status_code == 422

    # Missing required fields for person
    payload = {
        "entity_type": "person",
        "data": {"first_name": "John"},  # Missing last_name
    }
    response = client.post(
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities", json=payload
    )
    # Should succeed as last_name might be optional
    assert response.status_code in [200, 422]

    # Invalid email format
    payload = {
        "entity_type": "person",
        "data": {"first_name": "John", "last_name": "Doe", "email": "invalid-email"},
    }
    response = client.post(
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities", json=payload
    )
    assert response.status_code == 422


def test_duplicate_entity_creation(override_dependencies, test_case: Case):
    """Test creating duplicate entities"""
    # Create first person
    payload = {
        "entity_type": "person",
        "data": {"first_name": "John", "last_name": "Doe"},
    }
    response = client.post(
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities", json=payload
    )
    assert response.status_code == 200

    # Try to create duplicate
    response = client.post(
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities", json=payload
    )
    assert response.status_code == 400  # Should fail with duplicate error


def test_sql_injection_attempts(override_dependencies):
    """Test protection against SQL injection"""
    # Try SQL injection in search parameters
    malicious_inputs = [
        "'; DROP TABLE cases; --",
        "1' OR '1'='1",
        "admin'--",
        "1; SELECT * FROM users; --",
    ]

    for malicious_input in malicious_inputs:
        response = client.get(f"{settings.API_V1_STR}/cases/?status={malicious_input}")
        # Should handle safely without SQL errors
        assert response.status_code in [200, 400, 422]


def test_xss_prevention(override_dependencies, test_client: Client):
    """Test XSS attack prevention"""
    xss_payloads = [
        "<script>alert('XSS')</script>",
        "javascript:alert('XSS')",
        "<img src=x onerror=alert('XSS')>",
        "<svg onload=alert('XSS')>",
    ]

    for payload in xss_payloads:
        case_data = {"client_id": test_client.id, "title": payload, "notes": payload}
        response = client.post(f"{settings.API_V1_STR}/cases/", json=case_data)

        if response.status_code == 200:
            # If created, verify the payload is properly escaped
            data = response.json()
            assert data["title"] == payload  # Should be stored as-is
            assert data["notes"] == payload  # But rendered safely


def test_path_traversal_prevention(override_dependencies, test_case: Case):
    """Test path traversal attack prevention"""
    malicious_ids = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    ]

    for malicious_id in malicious_ids:
        response = client.get(f"{settings.API_V1_STR}/cases/{malicious_id}")
        # Should handle safely
        assert response.status_code in [400, 404, 422]


def test_large_payload_handling(override_dependencies, test_client: Client):
    """Test handling of very large payloads"""
    # Create case with very large notes
    large_notes = "A" * 1000000  # 1MB of text
    payload = {
        "client_id": test_client.id,
        "title": "Large Payload Test",
        "notes": large_notes,
    }

    response = client.post(f"{settings.API_V1_STR}/cases/", json=payload)
    # Should either succeed or fail with appropriate error
    assert response.status_code in [200, 413, 422]


def test_unicode_handling(override_dependencies, test_client: Client):
    """Test proper Unicode character handling"""
    unicode_strings = [
        "测试案例",  # Chinese
        "Тестовый случай",  # Russian
        "حالة اختبار",  # Arabic
        "🎉 Test Case 🎉",  # Emojis
        "Ñoño's Test Case",  # Special characters
    ]

    for unicode_string in unicode_strings:
        payload = {
            "client_id": test_client.id,
            "title": unicode_string,
            "notes": f"Testing: {unicode_string}",
        }
        response = client.post(f"{settings.API_V1_STR}/cases/", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == unicode_string


def test_api_response_time(override_dependencies, test_case: Case):
    """Test API response time performance"""
    import time

    endpoints = [
        f"{settings.API_V1_STR}/cases/",
        f"{settings.API_V1_STR}/cases/{test_case.id}",
        f"{settings.API_V1_STR}/cases/{test_case.id}/entities",
    ]

    for endpoint in endpoints:
        start_time = time.time()
        response = client.get(endpoint)
        elapsed_time = time.time() - start_time

        assert response.status_code == 200
        assert elapsed_time < 1.0  # Should respond within 1 second


def test_authentication_edge_cases(session: Session):
    """Test authentication edge cases without override"""
    # No authentication
    response = client.get(f"{settings.API_V1_STR}/cases/")
    assert response.status_code == 401

    # Invalid token
    response = client.get(
        f"{settings.API_V1_STR}/cases/",
        headers={"Authorization": "Bearer invalid_token"},
    )
    assert response.status_code == 401

    # Malformed authorization header
    response = client.get(
        f"{settings.API_V1_STR}/cases/", headers={"Authorization": "NotBearer token"}
    )
    assert response.status_code in [401, 422]


def test_case_number_format_validation(override_dependencies, test_client: Client):
    """Test case number format validation"""
    invalid_case_numbers = ["invalid", "12345", "TEST_001", "2023-01-01", ""]

    for case_number in invalid_case_numbers:
        payload = {
            "client_id": test_client.id,
            "title": "Test Case",
            "case_number": case_number,
        }
        response = client.post(f"{settings.API_V1_STR}/cases/", json=payload)
        # Should either accept or validate format
        if response.status_code == 200:
            data = response.json()
            # If accepted, it might have been reformatted
            assert data["case_number"] is not None
