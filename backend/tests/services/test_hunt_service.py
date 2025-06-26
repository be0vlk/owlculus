"""
Tests for HuntService
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from app.database.models import Case, Client, Hunt, HuntExecution, HuntStep, User
from app.hunts import BaseHunt
from app.services.hunt_service import HuntService
from sqlmodel import Session, select


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
        definition_json={"steps": [{"name": "step1", "description": "Test step"}]},
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

    @patch("app.services.hunt_service.HuntService._load_hunt_definitions")
    def test_init(self, mock_load_definitions, session: Session):
        """Test HuntService initialization."""
        service = HuntService(session)
        mock_load_definitions.assert_called_once()
        assert service.db is session

    def test_load_hunt_definitions(self, hunt_service: HuntService, session: Session):
        """Test loading hunt definitions from modules."""
        # Verify that hunt definitions were loaded during service initialization
        assert len(hunt_service._hunt_classes) > 0

        # Check that expected hunts are loaded (based on the logs we saw)
        assert "DomainHunt" in hunt_service._hunt_classes
        assert "PersonHunt" in hunt_service._hunt_classes

        # Verify that the loaded classes have the expected attributes
        for hunt_class in hunt_service._hunt_classes.values():
            assert hasattr(hunt_class, "__name__")

    def test_sync_hunts_to_db(self, hunt_service: HuntService, session: Session):
        """Test syncing hunt definitions to database."""

        # Setup a mock hunt class
        class MockHunt(BaseHunt):
            def __init__(self):
                super().__init__()
                self.name = "mock_hunt"
                self.display_name = "Mock Hunt"
                self.description = "Mock Hunt Description"
                self.category = "test"
                self.version = "1.0"

            def get_steps(self):
                return []

            def to_definition(self):
                return {"steps": []}

        # Add the mock hunt to the service
        hunt_service._hunt_classes = {"MockHunt": MockHunt}

        # Sync to DB
        hunt_service._sync_hunts_to_db()

        # Verify the hunt was created in the database using the service's session
        # The method uses the key name from _hunt_classes, which is "MockHunt"
        hunt = hunt_service.db.exec(select(Hunt).where(Hunt.name == "MockHunt")).first()
        assert hunt is not None
        assert hunt.display_name == "Mock Hunt"
        assert hunt.is_active is True

    @pytest.mark.asyncio
    async def test_list_hunts(
        self, hunt_service: HuntService, test_hunt: Hunt, test_user: User
    ):
        """Test listing available hunts."""
        hunts = await hunt_service.list_hunts(current_user=test_user)
        # The service loads DomainHunt and PersonHunt from definitions, plus our test hunt
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
        hunt = await hunt_service.get_hunt(9999, current_user=test_user)
        assert hunt is None

    @pytest.mark.asyncio
    @patch("app.services.hunt_service.HuntService._run_hunt_async")
    async def test_create_execution(
        self,
        mock_run_hunt_async,
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
        mock_run_hunt_async.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.core.dependencies.get_db")
    @patch("app.services.hunt_service.HuntExecutor")
    async def test_run_hunt_async(
        self,
        mock_executor_class,
        mock_get_db,
        hunt_service: HuntService,
        test_hunt_execution: HuntExecution,
        test_user: User,
        test_hunt: Hunt,
    ):
        """Test running a hunt asynchronously."""
        # Mock the database session generator
        mock_get_db.return_value = iter([hunt_service.db])

        # Setup mock executor
        mock_executor = AsyncMock()
        mock_executor_class.return_value = mock_executor

        # Run the async method
        await hunt_service._run_hunt_async(test_hunt_execution.id, test_user.id)

        # Verify the executor was called with the correct parameters
        mock_executor.execute_hunt.assert_awaited_once()
        assert mock_executor.execute_hunt.call_args[0][0].id == test_hunt_execution.id

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
    @patch("app.services.hunt_service.HuntExecutor")
    async def test_cancel_execution(
        self,
        mock_executor_class,
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
        mock_executor_class.return_value = mock_executor

        # Test cancelation
        execution = await hunt_service.cancel_execution(
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
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
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
        with pytest.raises(ValueError, match="Hunt not found or inactive"):
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
        with pytest.raises(ValueError, match="Hunt execution not found"):
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
            ValueError, match="Only running executions can be cancelled"
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

        # The @no_analyst decorator raises HTTPException, not PermissionError
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await hunt_service.create_execution(
                hunt_id=test_hunt.id,
                case_id=test_case.id,
                initial_parameters={},
                current_user=test_analyst,
            )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_run_hunt_async_error_handling(self, hunt_service: HuntService):
        """Test error handling in _run_hunt_async."""
        # Test with non-existent execution ID - should not raise an exception
        try:
            await hunt_service._run_hunt_async(9999, 1)
            # If we get here, the method handled the error gracefully
            assert True
        except Exception as e:
            # The method should handle errors gracefully and not let exceptions propagate
            pytest.fail(
                f"_run_hunt_async should handle errors gracefully, but got: {e}"
            )

    @pytest.mark.asyncio
    @patch("app.core.dependencies.get_db")
    @patch("app.services.hunt_service.HuntExecutor")
    async def test_run_hunt_async_execution_error(
        self,
        mock_executor_class,
        mock_get_db,
        hunt_service: HuntService,
        test_hunt_execution: HuntExecution,
        test_user: User,
        test_hunt: Hunt,
    ):
        """Test error handling during hunt execution."""
        # Mock the database session generator
        mock_get_db.return_value = iter([hunt_service.db])

        # Setup mock executor to raise an exception
        mock_executor = AsyncMock()
        mock_executor.execute_hunt.side_effect = Exception("Test error")
        mock_executor_class.return_value = mock_executor

        # Save the execution ID before calling async method
        execution_id = test_hunt_execution.id

        # Run the async method
        await hunt_service._run_hunt_async(execution_id, test_user.id)

        # Get the execution from the current session since _run_hunt_async uses its own session
        execution = hunt_service.db.get(HuntExecution, execution_id)

        # Verify the execution was marked as failed
        assert execution.status == "failed"
        assert execution.completed_at is not None
