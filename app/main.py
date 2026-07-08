import json
import logging
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from server.ws_manager import manager

# Agent & Engine imports
from agents.requirement_agent import extract_requirements
from agents.project_planner_agent import plan_project
from agents.code_generator_agent import generate_demo_project
from agents.file_generator_agent import generate_project_files
from agents.crud_generator_agent import generate_crud_app
from agents.frontend_generator_agent import generate_frontend
from agents.page_generator_agent import generate_pages
from agents.ai_backend_generator_agent import generate_backend
from agents.project_runner_agent import run_project
from agents.error_fix_agent import fix_project_errors
from agents.error_file_writer_agent import overwrite_project_files

# Meeting State imports
import server.meeting_state as meeting_state
from agents.meeting_connector_agent import classify_meeting_url

app = FastAPI(title="AI Meeting Agent Main App")

# Local directories
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
TRANSCRIPT_FILE = DATA_DIR / "live_transcript.txt"
REQUIREMENTS_FILE = DATA_DIR / "requirements.json"

logger = logging.getLogger(__name__)
LAST_PROJECT_PATH = None

class TranscriptRequest(BaseModel):
    transcript: str

def generate_demo_from_transcript(transcript: str) -> dict:
    """Runs the full requirement, planning, generation, and runner pipeline."""
    from server.ws_manager import manager
    manager.broadcast_sync({"action": "log", "message": "Started processing transcript."})
    
    # Write raw transcript to file for logs/watcher
    TRANSCRIPT_FILE.write_text(transcript, encoding="utf-8")
    
    # 1. Extract requirements
    manager.broadcast_sync({"action": "log", "message": "Extracting requirements..."})
    requirements = extract_requirements(transcript)
    if "error" in requirements:
        return {"success": False, "message": f"Requirement extraction error: {requirements['error']}"}

    # Write requirements JSON
    REQUIREMENTS_FILE.write_text(json.dumps(requirements, indent=4), encoding="utf-8")

    # 2. Plan project
    manager.broadcast_sync({"action": "log", "message": "Planning project architecture..."})
    plan = plan_project(requirements)

    # 3. Generate project base
    project = generate_demo_project(plan)
    project_path = project["project_path"]
    
    global LAST_PROJECT_PATH
    LAST_PROJECT_PATH = project_path

    # 4. Generate metadata & config
    manager.broadcast_sync({"action": "create_file", "path": "project_config.json", "content": json.dumps(requirements, indent=2)})
    generate_project_files(requirements, project_path)

    # 5. Generate backend app.py using AI
    manager.broadcast_sync({"action": "create_file", "path": "app.py", "content": "# Generated FastAPI backend\n"})
    generate_backend(requirements, project_path)

    # 6. Generate frontend index.html
    manager.broadcast_sync({"action": "create_file", "path": "index.html", "content": "<!-- Generated Frontend -->\n"})
    generate_frontend(requirements, project_path)

    # 7. Generate frontend pages HTML
    manager.broadcast_sync({"action": "log", "message": "Generating dynamic pages..."})
    generate_pages(requirements, project_path)

    # 8. Start the preview server and auto-heal errors
    from agents.autonomous_engine import run_autonomous_engine
    runner_result = run_autonomous_engine(project_path, max_iterations=3)

    features_list = requirements.get("features", [])
    pages_list = requirements.get("pages", [])
    proj_name = requirements.get("project_name") or requirements.get("project_title") or "AI Generated Project"
    running_url = "http://127.0.0.1:8001"

    formatted_msg = f"""Project Generated Successfully

Project Name: {proj_name}
Features Created: {", ".join(features_list)}
Pages Created: {", ".join(pages_list)}
Backend Status: {"Running" if runner_result.get("success") else "Failed"}
Frontend Status: {"Running" if runner_result.get("success") else "Failed"}
Running URL: {running_url}"""

    return {
        "success": runner_result.get("success", False),
        "message": formatted_msg,
        "running_url": running_url,
        "requirements": requirements,
        "details": {
            "project_name": proj_name,
            "features": features_list,
            "pages": pages_list,
            "backend_status": "Running" if runner_result.get("success") else "Failed",
            "frontend_status": "Running" if runner_result.get("success") else "Failed",
            "running_url": running_url
        }
    }

# ==========================================
# FastAPI Web Endpoints
# ==========================================

@app.websocket("/ws")
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
                                target=generate_demo_from_transcript,
                                args=(transcript,),
                                daemon=True
                            ).start()
                        else:
                            manager.broadcast_sync({"action": "log", "message": "No transcript available. Please join a meeting or provide audio first."})
                            
                    elif cmd == "update_project":
                        manager.broadcast_sync({"action": "log", "message": "Update Project command received (Feature pending integration)."})
                        
                    elif cmd == "fix_errors":
                        manager.broadcast_sync({"action": "log", "message": "Starting manual error fix loop..."})
                        if LAST_PROJECT_PATH:
                            from agents.autonomous_engine import run_autonomous_engine
                            threading.Thread(
                                target=run_autonomous_engine,
                                args=(LAST_PROJECT_PATH, 3),
                                daemon=True
                            ).start()
                        else:
                            manager.broadcast_sync({"action": "log", "message": "No active project found. Generate a project first."})
                            
                    elif cmd == "run_project":
                        manager.broadcast_sync({"action": "log", "message": "Running project..."})
                        if LAST_PROJECT_PATH:
                            from agents.project_runner_agent import run_project
                            threading.Thread(
                                target=run_project,
                                args=(LAST_PROJECT_PATH,),
                                daemon=True
                            ).start()
                        else:
                            manager.broadcast_sync({"action": "log", "message": "No active project found. Generate a project first."})
            except Exception as e:
                logger.error(f"WebSocket processing error: {e}")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/generate-demo")
def generate_demo(data: TranscriptRequest):
    result = generate_demo_from_transcript(data.transcript)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    return result

@app.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    """Transcribes an uploaded audio file and starts project generation."""
    try:
        suffix = Path(file.filename).suffix if file.filename else ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp:
            shutil.copyfileobj(file.file, temp)
            temp_path = temp.name
        
        # Load faster-whisper model
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        
        segments, info = model.transcribe(temp_path, beam_size=1)
        transcript = " ".join(s.text for s in segments)
        
        try:
            os.remove(temp_path)
        except Exception:
            pass

        if not transcript.strip():
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Could not extract any speech/transcript from the uploaded audio file."}
            )

        result = generate_demo_from_transcript(transcript)
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": f"Audio processing error: {e}"})

# ==========================================
# Meeting Lifecycle Endpoints
# ==========================================

def _run_meeting_lifecycle():
    try:
        meeting_state.start_runtime()
        while meeting_state.meeting_running and not meeting_state.stop_event.is_set():
            meeting_state.stop_event.wait(0.5)
    except Exception as exc:
        logger.exception("Meeting lifecycle interrupted: %s", exc)
    finally:
        if meeting_state.meeting_running and meeting_state.stop_event.is_set():
            meeting_state.end_meeting()
        meeting_state.meeting_thread = None

@app.post("/meeting/join")
def join_meeting(link: str = Form(...)):
    if not link:
        return {"success": False, "message": "Missing meeting link"}

    meeting_state.meeting_link = link
    meeting_state.meeting_type = classify_meeting_url(link)

    if not meeting_state.meeting_running:
        if meeting_state.meeting_thread is not None and meeting_state.meeting_thread.is_alive():
            return {"success": False, "message": "Meeting listener already running"}
            
        if not meeting_state.begin_meeting():
            return {"success": False, "message": "Failed to begin meeting state"}
            
        lifecycle_thread = threading.Thread(
            target=_run_meeting_lifecycle,
            name="meeting-lifecycle",
            daemon=True,
        )
        meeting_state.meeting_thread = lifecycle_thread
        lifecycle_thread.start()

    return {
        "success": True,
        "status": "joined",
        "meeting_type": meeting_state.meeting_type,
        "link": meeting_state.meeting_link,
    }

@app.post("/meeting/stop")
def stop_meeting():
    if not meeting_state.end_meeting():
        return {"success": False, "message": "Meeting already stopped"}
        
    # Read the final transcript and trigger demo generation on stop
    transcript = ""
    if TRANSCRIPT_FILE.exists():
        transcript = TRANSCRIPT_FILE.read_text(encoding="utf-8")
        
    if transcript.strip():
        # Trigger generation in a separate thread so this returns immediately
        threading.Thread(
            target=generate_demo_from_transcript,
            args=(transcript,),
            daemon=True
        ).start()
        return {"success": True, "message": "Meeting stopped. Generation pipeline started in background."}

    return {"success": True, "message": "Meeting stopped."}

@app.get("/meeting/status")
def get_meeting_status():
    transcript = ""
    if TRANSCRIPT_FILE.exists():
        transcript = TRANSCRIPT_FILE.read_text(encoding="utf-8")
        
    requirements = {}
    if REQUIREMENTS_FILE.exists():
        try:
            requirements = json.loads(REQUIREMENTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "running": meeting_state.meeting_running,
        "link": meeting_state.meeting_link,
        "transcript": transcript,
        "requirements": requirements
    }

# ==========================================
# Premium UI Page Dashboard
# ==========================================

@app.get("/", response_class=HTMLResponse)
def get_ui():
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Meeting Agent Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-grad: linear-gradient(135deg, #090d16 0%, #111827 50%, #1e1b4b 100%);
            --card-bg: rgba(22, 28, 45, 0.7);
            --card-border: rgba(255, 255, 255, 0.05);
            --accent: #6366f1;
            --accent-hover: #4f46e5;
            --accent-gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background: var(--bg-grad);
            color: var(--text-primary);
            min-height: 100vh;
            margin: 0;
            padding: 2rem;
            box-sizing: border-box;
        }

        .container {
            max-width: 1300px;
            margin: 0 auto;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2.5rem;
            border-bottom: 1px solid var(--card-border);
            padding-bottom: 1.5rem;
        }

        header h1 {
            font-size: 2.25rem;
            font-weight: 800;
            margin: 0;
            background: linear-gradient(to right, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        header p {
            color: var(--text-secondary);
            margin: 0.25rem 0 0 0;
            font-size: 1rem;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }

        @media (max-width: 1024px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background: var(--card-bg);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid var(--card-border);
            border-radius: 1rem;
            padding: 2rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }

        h2 {
            font-size: 1.25rem;
            font-weight: 600;
            margin: 0;
            color: #818cf8;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .tabs {
            display: flex;
            gap: 0.5rem;
            background: rgba(10, 15, 30, 0.5);
            padding: 4px;
            border-radius: 0.5rem;
            border: 1px solid var(--card-border);
        }

        .tab-btn {
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            padding: 10px;
            border-radius: 0.35rem;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.875rem;
            transition: all 0.2s;
        }

        .tab-btn.active {
            background: var(--accent);
            color: white;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }

        label {
            color: var(--text-secondary);
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        textarea {
            width: 100%;
            height: 120px;
            background: rgba(10, 15, 30, 0.4);
            border: 1px solid var(--card-border);
            border-radius: 0.5rem;
            color: white;
            padding: 12px;
            box-sizing: border-box;
            font-family: inherit;
            font-size: 0.9rem;
            resize: vertical;
            transition: border-color 0.2s;
        }

        textarea:focus {
            border-color: var(--accent);
            outline: none;
        }

        input[type="text"], input[type="file"] {
            width: 100%;
            background: rgba(10, 15, 30, 0.4);
            border: 1px solid var(--card-border);
            border-radius: 0.5rem;
            color: white;
            padding: 12px;
            box-sizing: border-box;
            font-family: inherit;
            font-size: 0.9rem;
            transition: border-color 0.2s;
        }

        input[type="text"]:focus {
            border-color: var(--accent);
            outline: none;
        }

        .btn {
            background: var(--accent-gradient);
            color: white;
            border: none;
            padding: 12px;
            border-radius: 0.5rem;
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            transition: opacity 0.2s, transform 0.1s;
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.2);
        }

        .btn:hover {
            opacity: 0.9;
        }

        .btn:active {
            transform: scale(0.98);
        }

        .btn.secondary {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--card-border);
            box-shadow: none;
        }

        .btn.secondary:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .live-status {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.85rem;
            font-weight: 600;
            background: rgba(10, 15, 30, 0.4);
            padding: 6px 12px;
            border-radius: 9999px;
            border: 1px solid var(--card-border);
        }

        .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #9ca3af;
        }

        .dot.active {
            background: #10b981;
            box-shadow: 0 0 8px #10b981;
            animation: pulse 1.5s infinite;
        }

        .console {
            background: #060913;
            border: 1px solid var(--card-border);
            border-radius: 0.5rem;
            padding: 1rem;
            font-family: monospace;
            font-size: 0.8rem;
            color: #34d399;
            height: 180px;
            overflow-y: auto;
            white-space: pre-wrap;
        }

        pre {
            background: #060913;
            border: 1px solid var(--card-border);
            border-radius: 0.5rem;
            padding: 1rem;
            font-family: monospace;
            font-size: 0.8rem;
            overflow-x: auto;
            margin: 0;
        }

        .success-box {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 0.5rem;
            padding: 1rem;
            color: #34d399;
            font-size: 0.9rem;
            white-space: pre-wrap;
            display: none;
        }

        .demo-frame-container {
            grid-column: span 2;
            display: none;
            flex-direction: column;
            gap: 1rem;
        }

        @media (max-width: 1024px) {
            .demo-frame-container {
                grid-column: span 1;
            }
        }

        iframe {
            width: 100%;
            height: 600px;
            border: 1px solid var(--card-border);
            border-radius: 0.75rem;
            background: white;
        }

        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.2); opacity: 0.5; }
            100% { transform: scale(1); opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>AI Meeting Agent</h1>
                <p>Generate functional CRUD demo projects directly from meeting conversations.</p>
            </div>
            <div class="live-status">
                <span id="status-dot" class="dot"></span>
                <span id="status-text">Status: Idle</span>
            </div>
        </header>

        <div class="dashboard-grid">
            <!-- Left Panel: Input -->
            <div class="card">
                <h2>⚡ Input Source</h2>
                <div class="tabs">
                    <button class="tab-btn active" onclick="switchTab('text')">Text Transcript</button>
                    <button class="tab-btn" onclick="switchTab('audio')">Upload Audio</button>
                    <button class="tab-btn" onclick="switchTab('meeting')">Join Meeting</button>
                </div>

                <!-- Tab: Text Transcript -->
                <div id="tab-text" class="tab-content active">
                    <div class="form-group">
                        <label for="transcript-text">Paste Transcript / Requirements</label>
                        <textarea id="transcript-text" placeholder="e.g. Create Employee Management System with Dashboard, Employee list, and Form page. Form page needs Name, Email, and Department..."></textarea>
                    </div>
                    <button class="btn" onclick="generateFromText()">Generate Demo Project</button>
                </div>

                <!-- Tab: Upload Audio -->
                <div id="tab-audio" class="tab-content">
                    <div class="form-group">
                        <label for="audio-file">Upload WAV / M4A Recording</label>
                        <input type="file" id="audio-file" accept=".wav,.m4a,.mp3">
                    </div>
                    <button class="btn" onclick="generateFromAudio()">Transcribe & Generate</button>
                </div>

                <!-- Tab: Join Meeting -->
                <div id="tab-meeting" class="tab-content">
                    <div class="form-group">
                        <label for="meeting-link">Google Meet / Zoom URL</label>
                        <input type="text" id="meeting-link" placeholder="https://meet.google.com/abc-defg-hij">
                    </div>
                    <div style="display: flex; gap: 1rem; margin-top: 1rem;">
                        <button id="join-btn" class="btn" onclick="joinMeeting()" style="flex: 1;">Start Listening</button>
                        <button id="stop-btn" class="btn secondary" onclick="stopMeeting()" style="flex: 1;" disabled>Stop Listening</button>
                    </div>
                </div>

                <h2>📝 Live Logs / Status</h2>
                <div id="log-console" class="console">Console ready. Select input and trigger generation.</div>
            </div>

            <!-- Right Panel: Output & Requirements -->
            <div class="card">
                <h2>🤖 Extracted Requirements</h2>
                <pre id="json-requirements">{}</pre>

                <h2>🚀 Generation Output</h2>
                <div id="success-message" class="success-box"></div>
                <div id="running-url-container" style="display: none; align-items: center; justify-content: space-between; background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 0.5rem; padding: 12px 16px;">
                    <div>
                        <span style="color: var(--text-secondary); font-size: 0.85rem; font-weight: 600;">RUNNING URL:</span>
                        <a id="demo-link" href="#" target="_blank" style="color: #818cf8; text-decoration: none; font-weight: 600; margin-left: 0.5rem; font-size: 1.05rem;">-</a>
                    </div>
                    <button class="btn" onclick="loadDemoIframe()" style="width: auto; padding: 6px 14px; font-size: 0.8rem;">Embed Live Preview</button>
                </div>
            </div>

            <!-- Full Width Iframe Embed -->
            <div id="demo-frame-container" class="card demo-frame-container">
                <h2>🌐 Live Project Preview</h2>
                <iframe id="demo-iframe" src=""></iframe>
            </div>
        </div>
    </div>

    <script>
        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById('tab-' + tab).classList.add('active');
        }

        function log(message) {
            const console = document.getElementById('log-console');
            console.textContent += '\\n' + message;
            console.scrollTop = console.scrollHeight;
        }

        function updateRequirements(json) {
            document.getElementById('json-requirements').textContent = JSON.stringify(json, null, 4);
        }

        async function generateFromText() {
            const text = document.getElementById('transcript-text').value;
            if (!text.strip && !text.trim()) {
                alert("Please enter transcript text.");
                return;
            }
            
            log("Sending transcript for generation...");
            document.getElementById('success-message').style.display = 'none';
            document.getElementById('running-url-container').style.display = 'none';
            document.getElementById('demo-frame-container').style.display = 'none';

            try {
                const response = await fetch('/generate-demo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ transcript: text })
                });
                
                const data = await response.json();
                if (response.ok) {
                    log("Project generated successfully!");
                    updateRequirements(data.requirements);
                    showSuccess(data.message, data.running_url);
                } else {
                    log("Error: " + data.detail);
                }
            } catch (err) {
                log("Network error: " + err);
            }
        }

        async function generateFromAudio() {
            const fileInput = document.getElementById('audio-file');
            if (fileInput.files.length === 0) {
                alert("Please select an audio file.");
                return;
            }

            const file = fileInput.files[0];
            const formData = new FormData();
            formData.append("file", file);

            log("Uploading audio file and starting transcription (this can take a few seconds)...");
            document.getElementById('success-message').style.display = 'none';
            document.getElementById('running-url-container').style.display = 'none';
            document.getElementById('demo-frame-container').style.display = 'none';

            try {
                const response = await fetch('/upload-audio', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                if (response.ok) {
                    log("Audio transcribed and project generated successfully!");
                    updateRequirements(data.requirements);
                    showSuccess(data.message, data.running_url);
                } else {
                    log("Error: " + data.message);
                }
            } catch (err) {
                log("Network error: " + err);
            }
        }

        async function joinMeeting() {
            const link = document.getElementById('meeting-link').value;
            if (!link) {
                alert("Please enter a meeting link.");
                return;
            }

            log("Joining meeting room: " + link);
            const formData = new FormData();
            formData.append("link", link);

            try {
                const response = await fetch('/meeting/join', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                if (data.success) {
                    log("Connected. Meeting Agent is listening to system/microphone audio...");
                    document.getElementById('join-btn').disabled = true;
                    document.getElementById('stop-btn').disabled = false;
                    pollMeetingStatus();
                } else {
                    log("Failed to join: " + data.message);
                }
            } catch (err) {
                log("Error joining meeting: " + err);
            }
        }

        async function stopMeeting() {
            log("Stopping meeting recorder...");
            try {
                const response = await fetch('/meeting/stop', { method: 'POST' });
                const data = await response.json();
                log(data.message);
                document.getElementById('join-btn').disabled = false;
                document.getElementById('stop-btn').disabled = true;
            } catch (err) {
                log("Error stopping meeting: " + err);
            }
        }

        function showSuccess(message, url) {
            const successBox = document.getElementById('success-message');
            successBox.textContent = message;
            successBox.style.display = 'block';

            document.getElementById('demo-link').href = url;
            document.getElementById('demo-link').textContent = url;
            document.getElementById('running-url-container').style.display = 'flex';
        }

        function loadDemoIframe() {
            const url = document.getElementById('demo-link').href;
            document.getElementById('demo-iframe').src = url;
            document.getElementById('demo-frame-container').style.display = 'flex';
        }

        async function pollMeetingStatus() {
            try {
                const response = await fetch('/meeting/status');
                const data = await response.json();
                
                const dot = document.getElementById('status-dot');
                const text = document.getElementById('status-text');
                
                if (data.running) {
                    dot.classList.add('active');
                    text.textContent = "Status: Listening Live...";
                    
                    if (data.transcript) {
                        document.getElementById('transcript-text').value = data.transcript;
                    }
                    if (data.requirements) {
                        updateRequirements(data.requirements);
                    }
                    
                    setTimeout(pollMeetingStatus, 2000);
                } else {
                    dot.classList.remove('active');
                    text.textContent = "Status: Idle";
                    document.getElementById('join-btn').disabled = false;
                    document.getElementById('stop-btn').disabled = true;
                }
            } catch (err) {
                console.error("Polling error: ", err);
            }
        }

        // Initial status check on page load
        pollMeetingStatus();
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)