import json
from typing import List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_message(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

    def broadcast_sync(self, message: dict):
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast_message(message))
        except RuntimeError:
            asyncio.run(self.broadcast_message(message))

manager = ConnectionManager()
