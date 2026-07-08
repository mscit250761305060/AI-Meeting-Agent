import logging
import threading

import server.meeting_state as meeting_state
from agents.audio_capture_agent import start_audio_capture
from meeting_engine.whisper_worker import start_whisper_worker

logger = logging.getLogger(__name__)


def ensure_runtime_started():
    if meeting_state.meeting_running:
        return True

    if not meeting_state.begin_meeting():
        return False

    return meeting_state.start_runtime()


def stop_runtime():
    if meeting_state.end_meeting():
        return True
    return False
