import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.database.models import User, Case, Client, Entity, CaseUserLink
from app.core.dependencies import get_current_active_user, get_db
from app.core.config import settings

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
    app.dependency_overrides[get_current_active_user] = get_current_user_override
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
    app.dependency_overrides[get_current_active_user] = (
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
    app.dependency_overrides[get_current_active_user] = (
        lambda: test_user
    )  # Return test user

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
    app.dependency_overrides[get_current_active_user] = (
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
