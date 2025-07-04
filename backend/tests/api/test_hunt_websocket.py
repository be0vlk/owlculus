"""
Tests for hunt WebSocket functionality
"""

from unittest.mock import AsyncMock

import pytest
from app.core.websocket_manager import websocket_manager
from app.database.models import HuntExecution


class TestHuntWebSocket:
    """Test WebSocket notifications for hunt executions"""

    @pytest.mark.asyncio
    async def test_websocket_progress_notifications(self):
        """Test that progress updates are sent via WebSocket"""
        execution_id = 1
        
        # Create a mock WebSocket
        mock_websocket = AsyncMock()
        
        # Connect the mock WebSocket
        await websocket_manager.connect(execution_id, mock_websocket)
        
        # Send progress update
        await websocket_manager.send_progress_update(execution_id, 0.5)
        
        # Verify the WebSocket received the message
        mock_websocket.send_json.assert_called_once_with({
            "event_type": "progress",
            "progress": 0.5,
            "execution_id": execution_id
        })
        
        # Clean up
        websocket_manager.disconnect(execution_id, mock_websocket)

    @pytest.mark.asyncio
    async def test_websocket_step_notifications(self):
        """Test that step completion notifications are sent"""
        execution_id = 1
        step_id = "step1"
        
        # Create a mock WebSocket
        mock_websocket = AsyncMock()
        
        # Connect the mock WebSocket
        await websocket_manager.connect(execution_id, mock_websocket)
        
        # Send step completion
        await websocket_manager.send_step_complete(execution_id, step_id, 0.33)
        
        # Verify the WebSocket received the message
        mock_websocket.send_json.assert_called_once_with({
            "event_type": "step_complete",
            "step_id": step_id,
            "progress": 0.33,
            "execution_id": execution_id
        })
        
        # Clean up
        websocket_manager.disconnect(execution_id, mock_websocket)

    @pytest.mark.asyncio
    async def test_websocket_multiple_connections(self):
        """Test that multiple WebSocket connections receive updates"""
        execution_id = 1
        
        # Create multiple mock WebSockets
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        
        # Connect both WebSockets
        await websocket_manager.connect(execution_id, mock_ws1)
        await websocket_manager.connect(execution_id, mock_ws2)
        
        # Send progress update
        await websocket_manager.send_progress_update(execution_id, 0.75)
        
        # Verify both WebSockets received the message
        expected_message = {
            "event_type": "progress",
            "progress": 0.75,
            "execution_id": execution_id
        }
        mock_ws1.send_json.assert_called_once_with(expected_message)
        mock_ws2.send_json.assert_called_once_with(expected_message)
        
        # Clean up
        websocket_manager.disconnect(execution_id, mock_ws1)
        websocket_manager.disconnect(execution_id, mock_ws2)

    @pytest.mark.asyncio
    async def test_websocket_completion_cleanup(self):
        """Test that WebSocket connections are cleaned up on completion"""
        execution_id = 1
        
        # Create a mock WebSocket
        mock_websocket = AsyncMock()
        
        # Connect the mock WebSocket
        await websocket_manager.connect(execution_id, mock_websocket)
        
        # Verify connection exists
        assert execution_id in websocket_manager.connections
        
        # Send completion notification
        await websocket_manager.send_execution_complete(execution_id)
        
        # Verify the WebSocket received the message
        mock_websocket.send_json.assert_called_once_with({
            "event_type": "complete",
            "execution_id": execution_id
        })
        
        # Verify connection was cleaned up
        assert execution_id not in websocket_manager.connections

    @pytest.mark.asyncio
    async def test_websocket_disconnected_client_handling(self):
        """Test that disconnected clients are handled gracefully"""
        execution_id = 1
        
        # Create a mock WebSocket that throws on send
        mock_websocket = AsyncMock()
        mock_websocket.send_json.side_effect = Exception("Connection closed")
        
        # Connect the mock WebSocket
        await websocket_manager.connect(execution_id, mock_websocket)
        
        # Send progress update - should not raise
        await websocket_manager.send_progress_update(execution_id, 0.5)
        
        # Verify the failed WebSocket was removed
        assert execution_id not in websocket_manager.connections or \
               mock_websocket not in websocket_manager.connections.get(execution_id, set())