"""
WebSocket connection manager for real-time notifications
"""

from typing import TYPE_CHECKING

from fastapi import WebSocket

if TYPE_CHECKING:
    from app.hunts.hunt_event import HuntEvent


class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""

    def __init__(self):
        # Dictionary mapping execution_id to set of WebSocket connections
        self.connections: dict[int, set[WebSocket]] = {}

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

    async def broadcast(self, event: "HuntEvent") -> None:
        """Send a hunt event to every connection for its execution."""
        connections = self.connections.get(event.execution_id, set()).copy()
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(event.to_wire())
            except Exception:  # noqa: BLE001 - transports can fail arbitrarily
                disconnected.append(websocket)

        for ws in disconnected:
            self.disconnect(event.execution_id, ws)

        if event.event_type in {"complete", "error"}:
            self.connections.pop(event.execution_id, None)


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
