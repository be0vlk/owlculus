import os
from datetime import timedelta

import pytest
from app.database import crud
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

# Set test environment variables before importing app
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_testing_only")
os.environ.setdefault("POSTGRES_USER", "test_user")
os.environ.setdefault("POSTGRES_PASSWORD", "test_password")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "test_db")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    get_password_hash,
    verify_access_token,
)
from app.database import models
from app.main import app

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
        is_superadmin=True,
    )
    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)
    return admin_user


@pytest.fixture(name="admin_user")
def admin_user_fixture(session):
    """Alias for test_admin fixture for compatibility"""
    admin_user = models.User(
        email="admin@test.com",
        username="admin",
        password_hash=get_password_hash("adminpass"),
        role="Admin",
        is_active=True,
        is_superadmin=True,
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


@pytest.fixture(name="test_investigator")
def test_investigator_fixture(session):
    investigator = models.User(
        email="investigator@test.com",
        username="investigator",
        password_hash=get_password_hash("investigatorpass"),
        role="Investigator",
        is_active=True,
    )
    session.add(investigator)
    session.commit()
    session.refresh(investigator)
    return investigator


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
    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.clear()


# Additional fixtures for comprehensive testing


@pytest.fixture(name="test_inactive_user")
def test_inactive_user_fixture(session):
    """Create an inactive user for testing authentication edge cases"""
    inactive_user = models.User(
        email="inactive@test.com",
        username="inactive",
        password_hash=get_password_hash("inactivepass"),
        role="User",
        is_active=False,
    )
    session.add(inactive_user)
    session.commit()
    session.refresh(inactive_user)
    return inactive_user


@pytest.fixture(name="test_client")
def test_client_fixture(session):
    """Create a test client (organization)"""
    client = models.Client(
        name="Test Organization", email="contact@testorg.com", phone="+1234567890"
    )
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


@pytest.fixture(name="test_case")
def test_case_fixture(session, test_client, test_admin):
    """Create a test case with a client"""
    case = models.Case(
        case_number="TEST-001",
        case_name="Test Investigation Case",
        case_description="A test case for unit testing",
        case_status="Open",
        case_notes="Initial test case notes",
        client_id=test_client.id,
        created_by_id=test_admin.id,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


@pytest.fixture(name="test_case_with_users")
def test_case_with_users_fixture(
    session, test_case, test_admin, test_user, test_analyst
):
    """Create a test case with multiple users assigned"""
    # Add users to case
    case_user_admin = models.CaseUserLink(case_id=test_case.id, user_id=test_admin.id)
    case_user_investigator = models.CaseUserLink(
        case_id=test_case.id, user_id=test_user.id
    )
    case_user_analyst = models.CaseUserLink(
        case_id=test_case.id, user_id=test_analyst.id
    )
    session.add(case_user_admin)
    session.add(case_user_investigator)
    session.add(case_user_analyst)
    session.commit()
    return test_case


@pytest.fixture(name="test_closed_case")
def test_closed_case_fixture(session, test_client, test_admin):
    """Create a closed test case"""
    case = models.Case(
        case_number="TEST-CLOSED-001",
        case_name="Closed Test Case",
        case_description="A closed test case",
        case_status="Closed",
        case_notes="Case has been closed",
        client_id=test_client.id,
        created_by_id=test_admin.id,
    )
    session.add(case)
    session.commit()
    session.refresh(case)
    return case


@pytest.fixture(name="test_entities")
def test_entities_fixture(session, test_case, test_admin):
    """Create various test entities of different types"""
    entities = []

    # Person entity
    person_entity = models.Entity(
        case_id=test_case.id,
        entity_type="person",
        data={
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "phone": "+1234567890",
            "address": {
                "street": "123 Main St",
                "city": "New York",
                "state": "NY",
                "country": "USA",
                "postal_code": "10001",
            },
        },
        created_by_id=test_admin.id,
    )
    entities.append(person_entity)

    # Company entity
    company_entity = models.Entity(
        case_id=test_case.id,
        entity_type="company",
        data={
            "name": "Test Corporation",
            "website": "https://testcorp.com",
            "phone": "+1987654321",
            "domains": ["testcorp.com", "testcorp.io"],
            "address": {
                "street": "456 Business Ave",
                "city": "San Francisco",
                "state": "CA",
                "country": "USA",
                "postal_code": "94105",
            },
        },
        created_by_id=test_admin.id,
    )
    entities.append(company_entity)

    # Domain entity
    domain_entity = models.Entity(
        case_id=test_case.id,
        entity_type="domain",
        data={
            "domain": "suspicious-domain.com",
            "description": "Potentially malicious domain",
        },
        created_by_id=test_admin.id,
    )
    entities.append(domain_entity)

    # IP Address entity
    ip_entity = models.Entity(
        case_id=test_case.id,
        entity_type="ip_address",
        data={"ip_address": "192.168.1.100", "description": "Internal network IP"},
        created_by_id=test_admin.id,
    )
    entities.append(ip_entity)

    for entity in entities:
        session.add(entity)
    session.commit()

    for entity in entities:
        session.refresh(entity)

    return entities


@pytest.fixture(name="test_evidence")
def test_evidence_fixture(session, test_case, test_admin):
    """Create test evidence files"""
    import os
    import tempfile

    # Create temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp_file:
        tmp_file.write(b"Test evidence content")
        tmp_file_path = tmp_file.name

    evidence = models.Evidence(
        case_id=test_case.id,
        evidence_name="test_evidence.txt",
        evidence_description="Test evidence file",
        evidence_type="document",
        file_path=tmp_file_path,
        file_size=21,  # Size of "Test evidence content"
        file_hash="abc123def456",
        uploaded_by_id=test_admin.id,
    )
    session.add(evidence)
    session.commit()
    session.refresh(evidence)

    # Clean up function
    def cleanup():
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

    # Return evidence and cleanup function
    return evidence, cleanup


@pytest.fixture(name="expired_token")
def expired_token_fixture():
    """Create an expired token for testing"""
    # Create token that expired 1 hour ago
    access_token = create_access_token(
        data={"sub": "expireduser"},
        expires_delta=timedelta(hours=-1),
    )
    return access_token


@pytest.fixture(name="invalid_token")
def invalid_token_fixture():
    """Create an invalid/malformed token for testing"""
    return "invalid.jwt.token"


@pytest.fixture(name="test_complete_scenario")
def test_complete_scenario_fixture(
    session,
    test_client,
    test_admin,
    test_user,
    test_analyst,
    test_case_with_users,
    test_entities,
    test_evidence,
):
    """Create a complete test scenario with all components"""
    return {
        "client": test_client,
        "case": test_case_with_users,
        "users": {
            "admin": test_admin,
            "investigator": test_user,
            "analyst": test_analyst,
        },
        "entities": test_entities,
        "evidence": test_evidence[0],  # Just the evidence object, not cleanup function
    }


@pytest.fixture(name="db_session")
def db_session_fixture(session):
    """Alias for session fixture for better readability in tests"""
    return session
