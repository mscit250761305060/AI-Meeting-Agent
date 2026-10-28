import json
import logging
import threading
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import manager
from app.services.project_service import ProjectGenerationService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

DATA_DIR = Path("data")
TRANSCRIPT_FILE = DATA_DIR / "live_transcript.txt"

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                cmd = msg.get("command")
                if cmd:
                    logger.info(f"Received WS command: {cmd}")
                    
                    if cmd == "generate_project":
                        transcript = TRANSCRIPT_FILE.read_text(encoding="utf-8") if TRANSCRIPT_FILE.exists() else ""
                        if transcript.strip():
                            manager.broadcast_sync({"action": "log", "message": "Starting project generation..."})
                            threading.Thread(
                                target=ProjectGenerationService.generate_demo_from_transcript,
                                args=(transcript,),
                                daemon=True
                            ).start()
                        else:
                            manager.broadcast_sync({"action": "log", "message": "No transcript available. Please join a meeting or provide audio first."})
                            
                    elif cmd == "update_project":
                        manager.broadcast_sync({"action": "log", "message": "Update Project command received (Feature pending integration)."})
                        
                    elif cmd == "fix_errors":
                        manager.broadcast_sync({"action": "log", "message": "Starting manual error fix loop..."})
                        last_path = ProjectGenerationService.get_last_project_path()
                        if last_path:
                            from agents.autonomous_engine import run_autonomous_engine
                            threading.Thread(
                                target=run_autonomous_engine,
                                args=(last_path, 3),
                                daemon=True
                            ).start()
                        else:
                            manager.broadcast_sync({"action": "log", "message": "No active project found. Generate a project first."})
                            
                    elif cmd == "run_project":
                        manager.broadcast_sync({"action": "log", "message": "Running project..."})
                        last_path = ProjectGenerationService.get_last_project_path()
                        if last_path:
                            from agents.project_runner_agent import run_project
                            threading.Thread(
                                target=run_project,
                                args=(last_path,),
                                daemon=True
                            ).start()
                        else:
                            manager.broadcast_sync({"action": "log", "message": "No active project found. Generate a project first."})
            except Exception as e:
                logger.error(f"WebSocket processing error: {e}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
