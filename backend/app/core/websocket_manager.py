"""
WebSocket connection manager for real-time notifications
"""

from typing import Dict, Set

from fastapi import WebSocket


class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""

    def __init__(self):
        # Dictionary mapping execution_id to set of WebSocket connections
        self.connections: Dict[int, Set[WebSocket]] = {}

    async def connect(self, execution_id: int, websocket: WebSocket):
        """Add a WebSocket connection for an execution"""
        if execution_id not in self.connections:
            self.connections[execution_id] = set()
        self.connections[execution_id].add(websocket)

    def disconnect(self, execution_id: int, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if execution_id in self.connections:
            self.connections[execution_id].discard(websocket)
            if not self.connections[execution_id]:
                del self.connections[execution_id]

    async def send_progress_update(
        self, execution_id: int, progress: float, step_id: str = None
    ):
        """Send progress update to all connected clients"""
        if execution_id not in self.connections:
            return

        message = {
            "event_type": "progress",
            "progress": progress,
            "execution_id": execution_id,
        }

        if step_id:
            message["step_id"] = step_id

        # Send to all connected clients
        disconnected = []
        for websocket in self.connections[execution_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected websockets
        for ws in disconnected:
            self.disconnect(execution_id, ws)

    async def send_step_complete(
        self, execution_id: int, step_id: str, progress: float
    ):
        """Send step completion notification"""
        if execution_id not in self.connections:
            return

        message = {
            "event_type": "step_complete",
            "step_id": step_id,
            "progress": progress,
            "execution_id": execution_id,
        }

        # Send to all connected clients
        disconnected = []
        for websocket in self.connections[execution_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected websockets
        for ws in disconnected:
            self.disconnect(execution_id, ws)

    async def send_step_failed(self, execution_id: int, step_id: str, progress: float):
        """Send step failure notification"""
        if execution_id not in self.connections:
            return

        message = {
            "event_type": "step_failed",
            "step_id": step_id,
            "progress": progress,
            "execution_id": execution_id,
        }

        # Send to all connected clients
        disconnected = []
        for websocket in self.connections[execution_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected websockets
        for ws in disconnected:
            self.disconnect(execution_id, ws)

    async def send_execution_complete(self, execution_id: int):
        """Send execution completion notification"""
        if execution_id not in self.connections:
            return

        message = {"event_type": "complete", "execution_id": execution_id}

        # Send to all connected clients
        disconnected = []
        for websocket in self.connections[execution_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected websockets
        for ws in disconnected:
            self.disconnect(execution_id, ws)

        # Remove all connections for this execution
        if execution_id in self.connections:
            del self.connections[execution_id]

    async def send_execution_error(self, execution_id: int, error: str):
        """Send execution error notification"""
        if execution_id not in self.connections:
            return

        message = {"event_type": "error", "error": error, "execution_id": execution_id}

        # Send to all connected clients
        disconnected = []
        for websocket in self.connections[execution_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected websockets
        for ws in disconnected:
            self.disconnect(execution_id, ws)

        # Remove all connections for this execution
        if execution_id in self.connections:
            del self.connections[execution_id]


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
