"""
Tests for HuntService
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlmodel import Session, select

from app.core.exceptions import (
    AuthorizationException,
    ResourceNotFoundException,
    ValidationException,
)
from app.database.models import Case, Client, Hunt, HuntExecution, HuntStep, User
from app.services.hunt_service import HuntService


@pytest.fixture(name="hunt_service")
def hunt_service_fixture(session: Session):
    """Fixture that provides a HuntService instance with a test database session."""
    return HuntService(session)


@pytest.fixture(name="test_user")
def test_user_fixture(session: Session):
    """Fixture that provides a test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        role="Investigator",
        is_active=True,
        is_superadmin=False,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="test_admin")
def test_admin_fixture(session: Session):
    """Fixture that provides a test admin user."""
    admin = User(
        username="adminuser",
        email="admin@example.com",
        password_hash="hashed_password",
        role="Admin",
        is_active=True,
        is_superadmin=True,
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)
    return admin


@pytest.fixture(name="test_analyst")
def test_analyst_fixture(session: Session):
    """Fixture that provides a test analyst user."""
    analyst = User(
        username="analystuser",
        email="analyst@example.com",
        password_hash="hashed_password",
        role="Analyst",
        is_active=True,
        is_superadmin=False,
    )
    session.add(analyst)
    session.commit()
    session.refresh(analyst)
    return analyst


@pytest.fixture(name="test_client")
def test_client_fixture(session: Session):
    """Fixture that provides a test client."""
    client = Client(name="Test Client", contact_email="client@example.com")
    session.add(client)
    session.commit()
    session.refresh(client)
    return client


@pytest.fixture(name="test_case")
def test_case_fixture(session: Session, test_client: Client, test_user: User):
    """Fixture that provides a test case."""
    case = Case(
        client_id=test_client.id,
        case_number="TEST-001",
        title="Test Case",
        status="Open",
        notes="Test case description",
    )
    session.add(case)
    session.commit()
    session.refresh(case)

    # Add the test user to the case
    from app.database.models import CaseUserLink

    case_user_link = CaseUserLink(case_id=case.id, user_id=test_user.id)
    session.add(case_user_link)
    session.commit()

    return case


@pytest.fixture(name="test_hunt")
def test_hunt_fixture(session: Session):
    """Fixture that provides a test hunt."""
    hunt = Hunt(
        name="test_hunt",
        display_name="Test Hunt",
        description="Test Hunt Description",
        category="test",
        version="1.0",
        definition_json={
            "steps": [],
            "initial_parameters": {"param1": {"type": "string"}},
        },
        is_active=True,
    )
    session.add(hunt)
    session.commit()
    session.refresh(hunt)
    return hunt


@pytest.fixture(name="test_hunt_execution")
def test_hunt_execution_fixture(
    session: Session, test_hunt: Hunt, test_case: Case, test_user: User
):
    """Fixture that provides a test hunt execution."""
    execution = HuntExecution(
        hunt_id=test_hunt.id,
        case_id=test_case.id,
        initial_parameters={"param1": "value1"},
        status="pending",
        created_by_id=test_user.id,
    )
    session.add(execution)
    session.commit()
    session.refresh(execution)
    return execution


class TestHuntService:
    """Test suite for HuntService."""

    def test_init_does_not_sync_definitions_per_request(self, session: Session):
        service = HuntService(session)

        assert service.db is session
        assert session.exec(select(Hunt)).all() == []

    @pytest.mark.asyncio
    async def test_list_hunts(
        self, hunt_service: HuntService, test_hunt: Hunt, test_user: User
    ):
        """Test listing available hunts."""
        hunts = await hunt_service.list_hunts(current_user=test_user)
        assert len(hunts) >= 1
        # Check that our test hunt is in the list
        hunt_names = [hunt.name for hunt in hunts]
        assert test_hunt.name in hunt_names

    @pytest.mark.asyncio
    async def test_get_hunt(
        self, hunt_service: HuntService, test_hunt: Hunt, test_user: User
    ):
        """Test getting a specific hunt by ID."""
        hunt = await hunt_service.get_hunt(test_hunt.id, current_user=test_user)
        assert hunt is not None
        assert hunt.id == test_hunt.id
        assert hunt.name == test_hunt.name

    @pytest.mark.asyncio
    async def test_get_hunt_not_found(self, hunt_service: HuntService, test_user: User):
        """Test getting a non-existent hunt."""
        with pytest.raises(ResourceNotFoundException, match="Hunt not found"):
            await hunt_service.get_hunt(9999, current_user=test_user)

    @pytest.mark.asyncio
    async def test_create_execution(
        self,
        hunt_service: HuntService,
        test_hunt: Hunt,
        test_case: Case,
        test_user: User,
    ):
        """Test creating a new hunt execution."""
        initial_params = {"param1": "value1"}
        execution = await hunt_service.create_execution(
            hunt_id=test_hunt.id,
            case_id=test_case.id,
            initial_parameters=initial_params,
            current_user=test_user,
        )

        assert execution is not None
        assert execution.hunt_id == test_hunt.id
        assert execution.case_id == test_case.id
        assert execution.initial_parameters == initial_params
        assert execution.status == "pending"
        assert execution.created_by_id == test_user.id
        assert execution.definition_snapshot == test_hunt.definition_json
        assert execution.implementation_build

    @pytest.mark.asyncio
    async def test_get_execution(
        self,
        hunt_service: HuntService,
        test_hunt_execution: HuntExecution,
        test_user: User,
    ):
        """Test getting a hunt execution."""
        execution = await hunt_service.get_execution(
            test_hunt_execution.id, current_user=test_user
        )
        assert execution is not None
        assert execution.id == test_hunt_execution.id

    @pytest.mark.asyncio
    async def test_list_case_executions(
        self,
        hunt_service: HuntService,
        test_hunt_execution: HuntExecution,
        test_user: User,
        test_case: Case,
    ):
        """Test listing executions for a case."""
        executions = await hunt_service.list_case_executions(
            test_case.id, current_user=test_user
        )
        assert len(executions) == 1
        assert executions[0].id == test_hunt_execution.id

    @pytest.mark.asyncio
    async def test_cancel_execution(
        self,
        hunt_service: HuntService,
        test_hunt_execution: HuntExecution,
        test_user: User,
    ):
        """Test canceling a running execution."""
        # Setup test execution in running state
        test_hunt_execution.status = "running"
        hunt_service.db.add(test_hunt_execution)
        hunt_service.db.commit()

        # Setup mock executor
        mock_executor = AsyncMock()
        mock_executor.cancel_execution = AsyncMock()

        # Mock the cancel_execution to update the status
        async def mock_cancel(exec_id):
            test_hunt_execution.status = "canceled"
            hunt_service.db.add(test_hunt_execution)
            hunt_service.db.commit()

        mock_executor.cancel_execution.side_effect = mock_cancel
        service = HuntService(
            hunt_service.db, executor_factory=lambda session: mock_executor
        )

        # Test cancelation
        execution = await service.cancel_execution(
            test_hunt_execution.id, current_user=test_user
        )

        # Verify the executor was called
        mock_executor.cancel_execution.assert_awaited_once_with(test_hunt_execution.id)
        assert execution.status == "canceled"

    @pytest.mark.asyncio
    async def test_get_execution_steps(
        self,
        hunt_service: HuntService,
        test_hunt_execution: HuntExecution,
        test_user: User,
        session: Session,
    ):
        """Test getting steps for an execution."""
        # Add test steps
        step1 = HuntStep(
            execution_id=test_hunt_execution.id,
            step_id="step1",
            plugin_name="TestPlugin",
            parameters={},
            status="completed",
            output={"result": "success"},
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        session.add(step1)
        session.commit()

        # Get steps
        steps = await hunt_service.get_execution_steps(
            test_hunt_execution.id, current_user=test_user
        )

        # Verify steps
        assert len(steps) == 1
        assert steps[0].step_id == "step1"
        assert steps[0].status == "completed"

    @pytest.mark.asyncio
    async def test_create_execution_nonexistent_hunt(
        self, hunt_service: HuntService, test_case: Case, test_user: User
    ):
        """Test creating an execution for a non-existent hunt."""
        with pytest.raises(
            ResourceNotFoundException, match="Hunt not found or inactive"
        ):
            await hunt_service.create_execution(
                hunt_id=9999,
                case_id=test_case.id,
                initial_parameters={},
                current_user=test_user,
            )

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_execution(
        self, hunt_service: HuntService, test_user: User
    ):
        """Test canceling a non-existent execution."""
        with pytest.raises(ResourceNotFoundException, match="Hunt execution not found"):
            await hunt_service.cancel_execution(9999, current_user=test_user)

    @pytest.mark.asyncio
    async def test_cancel_completed_execution(
        self,
        hunt_service: HuntService,
        test_hunt_execution: HuntExecution,
        test_user: User,
    ):
        """Test canceling an already completed execution."""
        test_hunt_execution.status = "completed"
        hunt_service.db.add(test_hunt_execution)
        hunt_service.db.commit()

        with pytest.raises(
            ValidationException, match="Only running executions can be cancelled"
        ):
            await hunt_service.cancel_execution(
                test_hunt_execution.id, current_user=test_user
            )

    @pytest.mark.asyncio
    async def test_analyst_cannot_create_execution(
        self,
        hunt_service: HuntService,
        test_hunt: Hunt,
        test_case: Case,
        test_analyst: User,
        session: Session,
    ):
        """Test that analysts cannot create hunt executions."""
        # Add analyst to the case first so they have access
        from app.database.models import CaseUserLink

        case_user_link = CaseUserLink(case_id=test_case.id, user_id=test_analyst.id)
        session.add(case_user_link)
        session.commit()

        with pytest.raises(AuthorizationException, match="Not authorized"):
            await hunt_service.create_execution(
                hunt_id=test_hunt.id,
                case_id=test_case.id,
                initial_parameters={},
                current_user=test_analyst,
            )
