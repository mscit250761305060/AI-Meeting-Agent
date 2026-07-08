import json
import logging
import threading
from pathlib import Path

from fastapi import FastAPI

import server.meeting_state as meeting_state
from agents.meeting_connector_agent import classify_meeting_url

app = FastAPI()

logger = logging.getLogger(__name__)
REQUIREMENTS_FILE = Path("data/requirements.json")


@app.get("/health")
def health():
    return {"status": "running"}


@app.get("/requirements")
def get_requirements():
    if not REQUIREMENTS_FILE.exists():
        return {}

    return json.loads(REQUIREMENTS_FILE.read_text(encoding="utf-8"))


def _run_meeting_lifecycle():
    logger.info("Meeting lifecycle started")

    try:
        meeting_state.start_runtime()
        while meeting_state.meeting_running and not meeting_state.stop_event.is_set():
            meeting_state.stop_event.wait(0.5)
    except RuntimeError as exc:
        logger.exception("Meeting lifecycle interrupted: %s", exc)
    finally:
        if meeting_state.meeting_running and meeting_state.stop_event.is_set():
            meeting_state.end_meeting()
        meeting_state.meeting_thread = None
        logger.info("Meeting lifecycle stopped")


@app.post("/meeting/join")
def join_meeting(link: str):
    if not link:
        return {"status": "missing link"}

    meeting_state.meeting_link = link
    meeting_state.meeting_type = classify_meeting_url(link)

    if not meeting_state.meeting_running:
        start_meeting()

    return {
        "status": "joined",
        "meeting_type": meeting_state.meeting_type,
        "link": meeting_state.meeting_link,
    }


@app.post("/meeting/start")
def start_meeting():
    if meeting_state.meeting_running:
        return {"status": "already running"}

    if meeting_state.meeting_thread is not None and meeting_state.meeting_thread.is_alive():
        return {"status": "already running"}

    if not meeting_state.begin_meeting():
        return {"status": "already running"}

    lifecycle_thread = threading.Thread(
        target=_run_meeting_lifecycle,
        name="meeting-lifecycle",
        daemon=True,
    )
    meeting_state.meeting_thread = lifecycle_thread
    lifecycle_thread.start()

    logger.info("Meeting Started")

    return {"status": "meeting started"}


@app.post("/meeting/stop")
def stop_meeting():
    if not meeting_state.end_meeting():
        return {"status": "already stopped"}

    logger.info("Meeting Stopped")

    return {"status": "meeting stopped"}


@app.get("/meeting/status")
def meeting_status():
    return {"running": meeting_state.meeting_running}