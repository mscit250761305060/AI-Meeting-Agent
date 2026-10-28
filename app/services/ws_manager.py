import json
import asyncio
import logging
from typing import List, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        try:
            self._loop = asyncio.get_running_loop()
        except Exception:
            pass

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_message(self, message: dict):
        dead_connections = []
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for dc in dead_connections:
            self.disconnect(dc)

    def broadcast_sync(self, message: dict):
        if not self.active_connections:
            return

        try:
            current_loop = asyncio.get_running_loop()
            if current_loop == self._loop and current_loop.is_running():
                current_loop.create_task(self.broadcast_message(message))
                return
        except RuntimeError:
            pass

        if self._loop and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self.broadcast_message(message), self._loop)
                return
            except Exception as e:
                logger.debug(f"Threadsafe broadcast failed: {e}")

        try:
            asyncio.run(self.broadcast_message(message))
        except Exception:
            pass

manager = ConnectionManager()
