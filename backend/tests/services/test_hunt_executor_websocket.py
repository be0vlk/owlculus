"""
Tests for hunt executor WebSocket integration
"""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from app.core.websocket_manager import websocket_manager
from app.database.models import HuntExecution, HuntStep, User
from app.hunts.base_hunt import HuntStepDefinition
from app.hunts.hunt_executor import HuntExecutor


class TestHuntExecutorWebSocket:
    """Test that hunt executor sends WebSocket notifications"""

    @pytest.mark.asyncio
    async def test_executor_sends_progress_updates(self, db_session):
        """Test that the executor sends progress updates via WebSocket"""
        # Patch the websocket_manager methods
        with patch.object(websocket_manager, 'send_progress_update', new_callable=AsyncMock) as mock_progress, \
             patch.object(websocket_manager, 'send_step_complete', new_callable=AsyncMock) as mock_step_complete, \
             patch.object(websocket_manager, 'send_execution_complete', new_callable=AsyncMock) as mock_complete:
            
            # Create test data
            user = User(id=1, username="test", email="test@test.com", password_hash="hash", role="Admin")
            execution = HuntExecution(
                id=1,
                hunt_id=1,
                case_id=1,
                status="running",
                progress=0.0,
                initial_parameters={},
                created_by_id=1
            )
            
            # Create hunt definition with 2 steps
            hunt_definition = {
                "steps": [
                    {
                        "step_id": "step1",
                        "plugin_name": "test_plugin",
                        "display_name": "Test Step 1",
                        "description": "First test step",
                        "depends_on": [],
                        "parameter_mapping": {},
                        "static_parameters": {},
                        "save_to_case": False,
                        "optional": False
                    },
                    {
                        "step_id": "step2", 
                        "plugin_name": "test_plugin",
                        "display_name": "Test Step 2",
                        "description": "Second test step",
                        "depends_on": ["step1"],
                        "parameter_mapping": {},
                        "static_parameters": {},
                        "save_to_case": False,
                        "optional": False
                    }
                ]
            }
            
            # Mock plugin service
            mock_plugin = AsyncMock()
            
            # Create an async generator for execute_with_evidence_collection
            async def mock_execute(params):
                yield {"type": "data", "data": {"result": "test"}}
            
            mock_plugin.execute_with_evidence_collection = mock_execute
            
            executor = HuntExecutor(db_session)
            executor.plugin_service.get_plugin = MagicMock(return_value=mock_plugin)
            
            # Mock database operations
            db_session.add = MagicMock()
            db_session.commit = MagicMock()
            db_session.get = MagicMock(return_value=None)
            
            # Execute hunt
            await executor.execute_hunt(execution, hunt_definition, user)
            
            # Verify progress updates were sent
            # Should have called send_progress_update at least twice (once per step start)
            assert mock_progress.call_count >= 2
            
            # Should have called send_step_complete for each step
            assert mock_step_complete.call_count == 2
            
            # Should have called send_execution_complete
            mock_complete.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_executor_sends_step_failure_notification(self, db_session):
        """Test that the executor sends step failure notifications"""
        # Patch the websocket_manager methods
        with patch.object(websocket_manager, 'send_step_failed', new_callable=AsyncMock) as mock_step_failed, \
             patch.object(websocket_manager, 'send_progress_update', new_callable=AsyncMock) as mock_progress, \
             patch.object(websocket_manager, 'send_execution_complete', new_callable=AsyncMock) as mock_complete:
            
            # Create test data
            user = User(id=1, username="test", email="test@test.com", password_hash="hash", role="Admin")
            execution = HuntExecution(
                id=1,
                hunt_id=1,
                case_id=1,
                status="running",
                progress=0.0,
                initial_parameters={},
                created_by_id=1
            )
            
            # Create hunt definition with a step that will fail
            hunt_definition = {
                "steps": [
                    {
                        "step_id": "step1",
                        "plugin_name": "failing_plugin",
                        "display_name": "Failing Step",
                        "description": "Step that will fail",
                        "depends_on": [],
                        "parameter_mapping": {},
                        "static_parameters": {},
                        "save_to_case": False,
                        "optional": False  # Required step
                    }
                ]
            }
            
            # Mock plugin service to raise an exception during execution
            mock_plugin = AsyncMock()
            async def mock_execute_fail(params):
                raise Exception("Plugin execution failed")
                yield  # This won't be reached
            
            mock_plugin.execute_with_evidence_collection = mock_execute_fail
            
            executor = HuntExecutor(db_session)
            executor.plugin_service.get_plugin = MagicMock(return_value=mock_plugin)
            
            # Mock database operations
            db_session.add = MagicMock()
            db_session.commit = MagicMock()
            db_session.get = MagicMock(return_value=None)
            
            # Execute hunt - should complete but mark execution as partial due to failed required step
            await executor.execute_hunt(execution, hunt_definition, user)
            
            # Verify step failure notification was sent
            mock_step_failed.assert_called_once()
            call_args = mock_step_failed.call_args
            assert call_args[0][0] == 1  # execution_id
            assert call_args[0][1] == "step1"  # step_id
            assert call_args[0][2] == 0.0  # progress (0 steps completed)
            
            # Verify execution was marked as partial (not fully completed)
            assert execution.status == "partial"