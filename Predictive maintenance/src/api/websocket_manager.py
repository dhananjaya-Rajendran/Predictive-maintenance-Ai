"""
WebSocket Connection Manager for Real-Time Streaming Telemetry and Alert Broadcasts.
"""
from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio


class WebSocketManager:
    """
    Manages active WebSocket connections and handles live event multicasting.
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_json(self, data: Dict[str, Any]):
        """
        Multicasts JSON payload to all active browser clients.
        """
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception:
                disconnected.append(connection)

        for dead_conn in disconnected:
            self.disconnect(dead_conn)


WS_MANAGER = WebSocketManager()
