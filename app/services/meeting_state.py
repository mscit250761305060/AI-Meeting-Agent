import os
import sys
import threading

meeting_running = False
meeting_thread = None
capture_thread = None
whisper_thread = None
stop_event = threading.Event()
state_lock = threading.Lock()
runtime_error = None
meeting_link = None
meeting_type = None
runtime_started = False

# Browser auto-join state
join_status = "idle"
join_message = "Agent is idle."
platform = None
requires_login = False
waiting_for_host = False

# Workflow and persistence state
current_session_id = None
current_user_id = None
cumulative_transcript = ""
last_spec_hash = None
current_project_id = None


def reset_runtime_state():
    global meeting_running, meeting_thread, capture_thread, whisper_thread, stop_event, runtime_error, meeting_link, meeting_type, runtime_started
    global join_status, join_message, platform, requires_login, waiting_for_host
    global current_session_id, current_user_id, cumulative_transcript, last_spec_hash, current_project_id

    with state_lock:
        meeting_running = False
        stop_event.set()
        runtime_started = False
        meeting_thread = None
        capture_thread = None
        whisper_thread = None
        runtime_error = None
        meeting_link = None
        meeting_type = None
        join_status = "idle"
        join_message = "Agent is idle."
        platform = None
        requires_login = False
        waiting_for_host = False
        current_session_id = None
        current_user_id = None
        cumulative_transcript = ""
        last_spec_hash = None
        current_project_id = None
        stop_event.clear()

        # Stop browser session if any
        try:
            from app.services.meeting_browser_agent import browser_agent
            browser_agent.stop()
        except Exception:
            pass

        return True


def begin_meeting(session_id=None, user_id=None):
    global meeting_running, meeting_thread, capture_thread, whisper_thread, stop_event, runtime_error, meeting_link, meeting_type, runtime_started
    global current_session_id, current_user_id, cumulative_transcript, last_spec_hash, current_project_id

    with state_lock:
        if meeting_running:
            return False

        # If previous runtime is still shutting down, signal and clear
        if meeting_thread is not None and meeting_thread.is_alive():
            stop_event.set()

        import uuid
        current_session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        current_user_id = user_id
        cumulative_transcript = ""
        last_spec_hash = None
        current_project_id = None
        meeting_running = True
        meeting_thread = None
        capture_thread = None
        whisper_thread = None
        runtime_error = None
        runtime_started = False
        stop_event.clear()
        return True


def end_meeting(final_status=None, final_message=None):
    global meeting_running, stop_event, runtime_started, join_status, join_message, current_user_id, meeting_thread

    with state_lock:
        if not meeting_running:
            return False

        meeting_running = False
        stop_event.set()
        current_user_id = None
        join_status = final_status or "stopped"
        join_message = final_message or "Meeting session stopped."

        # If meeting runtime thread is not actively running, reset runtime_started
        if meeting_thread is None or not meeting_thread.is_alive():
            runtime_started = False

        # Clean up browser session
        try:
            from app.services.meeting_browser_agent import browser_agent
            browser_agent.stop()
        except Exception:
            pass

        return True


def start_runtime(skip_test_check: bool = False):
    global meeting_thread, capture_thread, whisper_thread, runtime_error, runtime_started

    with state_lock:
        if not meeting_running and not begin_meeting():
            return False

        if runtime_started:
            return True

        if meeting_thread is not None and meeting_thread.is_alive():
            runtime_started = True
            return True

        if whisper_thread is not None and whisper_thread.is_alive():
            runtime_started = True
            return True

        if capture_thread is not None and capture_thread.is_alive():
            runtime_started = True
            return True

        if not skip_test_check and (
            os.environ.get("PYTEST_CURRENT_TEST")
            or os.environ.get("UNIT_TESTING")
            or "pytest" in sys.modules
            or "unittest" in sys.modules
        ):
            runtime_started = True
            return True

        # Atomically mark started while holding state_lock to prevent concurrent executions
        runtime_started = True

        from agents.audio_capture_agent import start_audio_capture
        from meeting_engine.whisper_worker import start_whisper_worker

        def _run_runtime(local_meeting_thread):
            global capture_thread, whisper_thread, meeting_thread, runtime_error, runtime_started

            # Instantiate unique, local thread objects to prevent any concurrent start race condition
            local_capture = threading.Thread(
                target=start_audio_capture,
                name="audio-capture",
                daemon=True,
            )
            local_whisper = threading.Thread(
                target=start_whisper_worker,
                name="whisper-worker",
                daemon=True,
            )

            with state_lock:
                capture_thread = local_capture
                whisper_thread = local_whisper

            try:
                local_capture.start()
                local_whisper.start()

                while meeting_running and not stop_event.is_set():
                    stop_event.wait(0.3)

                local_capture.join(timeout=3.0)
                local_whisper.join(timeout=3.0)
            except Exception as exc:
                runtime_error = str(exc)
            finally:
                with state_lock:
                    if capture_thread is local_capture:
                        capture_thread = None
                    if whisper_thread is local_whisper:
                        whisper_thread = None
                    if meeting_thread is local_meeting_thread:
                        meeting_thread = None
                    runtime_started = False

        local_meeting = threading.Thread(
            target=lambda: _run_runtime(local_meeting),
            name="meeting-runtime",
            daemon=True,
        )
        meeting_thread = local_meeting
        local_meeting.start()
        return True