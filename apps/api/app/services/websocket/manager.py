"""
WebSocket Connection Manager

Manages WebSocket connections for real-time progress updates.
Supports Socket.IO for frontend communication.
"""

import logging
from typing import Dict, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio

try:
    import socketio
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    socketio = None

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for progress updates
    
    Supports both FastAPI WebSocket and Socket.IO
    """
    
    def __init__(self):
        """Initialize WebSocket manager"""
        # FastAPI WebSocket connections
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Socket.IO server (if available)
        if SOCKETIO_AVAILABLE:
            self.sio = socketio.AsyncServer(
                cors_allowed_origins="*",
                async_mode="asgi"
            )
        else:
            self.sio = None
            logger.warning("socketio not available. Install with: pip install python-socketio")
        
        # Connection tracking
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of connection_ids
        self.connection_users: Dict[str, str] = {}  # connection_id -> user_id
        
        logger.info("WebSocket Manager initialized")
    
    async def connect(self, websocket: WebSocket, user_id: str, connection_id: Optional[str] = None):
        """
        Connect a WebSocket client
        
        Args:
            websocket: FastAPI WebSocket connection
            user_id: User ID
            connection_id: Optional connection ID (auto-generated if None)
        """
        if connection_id is None:
            import uuid
            connection_id = str(uuid.uuid4())
        
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        self.connection_users[connection_id] = user_id
        
        logger.info(f"WebSocket connected: {connection_id} for user {user_id}")
    
    async def disconnect(self, connection_id: str):
        """Disconnect a WebSocket client"""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.close()
            except Exception:
                pass
            del self.active_connections[connection_id]
        
        if connection_id in self.connection_users:
            user_id = self.connection_users[connection_id]
            if user_id in self.user_connections:
                self.user_connections[user_id].discard(connection_id)
                if not self.user_connections[user_id]:
                    del self.user_connections[user_id]
            del self.connection_users[connection_id]
        
        logger.info(f"WebSocket disconnected: {connection_id}")
    
    async def send_to_user(
        self,
        user_id: str,
        event: str,
        data: Dict,
    ):
        """
        Send message to all connections for a user
        
        Args:
            user_id: User ID
            event: Event name (e.g., "generation:progress")
            data: Event data
        """
        if user_id not in self.user_connections:
            return
        
        message = {
            "event": event,
            "data": data,
        }
        
        # Send via FastAPI WebSocket
        disconnected = []
        for connection_id in self.user_connections[user_id]:
            if connection_id in self.active_connections:
                try:
                    websocket = self.active_connections[connection_id]
                    await websocket.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send to {connection_id}: {e}")
                    disconnected.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected:
            await self.disconnect(connection_id)
        
        # Send via Socket.IO if available
        if self.sio:
            try:
                await self.sio.emit(event, data, room=user_id)
            except Exception as e:
                logger.error(f"Socket.IO emit failed: {e}")
    
    async def send_generation_progress(
        self,
        user_id: str,
        generation_id: str,
        progress: int,
        message: str,
        metadata: Optional[Dict] = None,
    ):
        """
        Send generation progress update
        
        Args:
            user_id: User ID
            generation_id: Generation job ID
            progress: Progress percentage (0-100)
            message: Progress message
            metadata: Optional metadata
        """
        await self.send_to_user(
            user_id,
            "generation:progress",
            {
                "generation_id": generation_id,
                "progress": progress,
                "message": message,
                "metadata": metadata or {},
            }
        )
    
    async def send_training_progress(
        self,
        user_id: str,
        identity_id: str,
        progress: int,
        message: str,
        metadata: Optional[Dict] = None,
    ):
        """
        Send training progress update
        
        Args:
            user_id: User ID
            identity_id: Identity ID
            progress: Progress percentage (0-100)
            message: Progress message
            metadata: Optional metadata
        """
        await self.send_to_user(
            user_id,
            "training:progress",
            {
                "identity_id": identity_id,
                "progress": progress,
                "message": message,
                "metadata": metadata or {},
            }
        )
    
    async def send_task_complete(
        self,
        user_id: str,
        task_id: str,
        task_type: str,
        result: Dict,
    ):
        """
        Send task completion notification
        
        Args:
            user_id: User ID
            task_id: Task ID
            task_type: Task type ("generation" or "training")
            result: Task result
        """
        await self.send_to_user(
            user_id,
            f"{task_type}:complete",
            {
                "task_id": task_id,
                "result": result,
            }
        )
    
    def get_connection_count(self, user_id: Optional[str] = None) -> int:
        """Get connection count (for user or total)"""
        if user_id:
            return len(self.user_connections.get(user_id, set()))
        return len(self.active_connections)


# ==================== GLOBAL INSTANCE ====================

_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create WebSocket manager singleton"""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager
