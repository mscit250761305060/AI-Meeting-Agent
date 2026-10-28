import threading
import time
import pytest
from unittest.mock import patch, MagicMock

from app.services import meeting_state


@pytest.fixture(autouse=True)
def clean_runtime():
    """Ensure runtime state is fully reset before and after each test."""
    meeting_state.reset_runtime_state()
    yield
    meeting_state.reset_runtime_state()


def test_concurrent_start_runtime_prevents_duplicate_threads_and_no_keyerror():
    """
    Verify that when multiple concurrent threads call start_runtime simultaneously,
    exactly ONE meeting-runtime, audio-capture, and whisper-worker thread is started,
    and no KeyError / Thread._bootstrap exception is raised.
    """
    meeting_state.begin_meeting("session_concurrent_test")

    started_count = {"audio": 0, "whisper": 0}
    lock = threading.Lock()

    def mock_audio():
        with lock:
            started_count["audio"] += 1
        while meeting_state.meeting_running and not meeting_state.stop_event.is_set():
            time.sleep(0.05)

    def mock_whisper():
        with lock:
            started_count["whisper"] += 1
        while meeting_state.meeting_running and not meeting_state.stop_event.is_set():
            time.sleep(0.05)

    with patch("agents.audio_capture_agent.start_audio_capture", side_effect=mock_audio), \
         patch("meeting_engine.whisper_worker.start_whisper_worker", side_effect=mock_whisper):

        errors = []
        threads = []

        def caller():
            try:
                res = meeting_state.start_runtime(skip_test_check=True)
                assert res is True
            except Exception as exc:
                errors.append(exc)

        # Launch 10 threads concurrently trying to start_runtime at the exact same millisecond
        for _ in range(10):
            t = threading.Thread(target=caller)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent start_runtime raised errors: {errors}"

        # Wait a moment for the runtime thread to initialize its workers
        time.sleep(0.2)

        with meeting_state.state_lock:
            assert meeting_state.runtime_started is True
            assert meeting_state.meeting_thread is not None
            assert meeting_state.whisper_thread is not None
            assert meeting_state.capture_thread is not None
            assert meeting_state.meeting_thread.is_alive()
            assert meeting_state.whisper_thread.is_alive()
            assert meeting_state.capture_thread.is_alive()

        # Crucially: audio and whisper workers were started EXACTLY once, not 10 times
        assert started_count["audio"] == 1
        assert started_count["whisper"] == 1

        # Now cleanly stop
        meeting_state.end_meeting()
        time.sleep(0.3)

        with meeting_state.state_lock:
            assert meeting_state.meeting_running is False
            assert not meeting_state.meeting_thread.is_alive() if meeting_state.meeting_thread else True


def test_start_runtime_idempotency_when_workers_already_alive():
    """
    Verify calling start_runtime repeatedly when workers are alive returns True
    without attempting duplicate thread startups.
    """
    meeting_state.begin_meeting("session_idempotent_test")

    def mock_audio():
        while meeting_state.meeting_running and not meeting_state.stop_event.is_set():
            time.sleep(0.05)

    def mock_whisper():
        while meeting_state.meeting_running and not meeting_state.stop_event.is_set():
            time.sleep(0.05)

    with patch("agents.audio_capture_agent.start_audio_capture", side_effect=mock_audio), \
         patch("meeting_engine.whisper_worker.start_whisper_worker", side_effect=mock_whisper):

        res1 = meeting_state.start_runtime(skip_test_check=True)
        assert res1 is True
        time.sleep(0.1)

        # Subsequent calls must succeed immediately and not recreate or restart threads
        initial_whisper = meeting_state.whisper_thread
        initial_capture = meeting_state.capture_thread

        res2 = meeting_state.start_runtime(skip_test_check=True)
        assert res2 is True
        assert meeting_state.whisper_thread is initial_whisper
        assert meeting_state.capture_thread is initial_capture

        res3 = meeting_state.start_runtime(skip_test_check=True)
        assert res3 is True
        assert meeting_state.whisper_thread is initial_whisper

        meeting_state.end_meeting()


def test_meeting_lifecycle_clean_restart_cycle():
    """
    Verify that ending a meeting and starting a new one cleans up prior worker
    threads and starts a fresh, isolated worker thread safely.
    """
    def mock_worker():
        while meeting_state.meeting_running and not meeting_state.stop_event.is_set():
            time.sleep(0.05)

    with patch("agents.audio_capture_agent.start_audio_capture", side_effect=mock_worker), \
         patch("meeting_engine.whisper_worker.start_whisper_worker", side_effect=mock_worker):

        # Cycle 1
        meeting_state.begin_meeting("session_cycle_1")
        meeting_state.start_runtime(skip_test_check=True)
        time.sleep(0.1)
        assert meeting_state.whisper_thread is not None
        assert meeting_state.whisper_thread.is_alive()

        meeting_state.end_meeting()
        time.sleep(0.3)
        assert meeting_state.meeting_running is False

        # Cycle 2
        meeting_state.begin_meeting("session_cycle_2")
        meeting_state.start_runtime(skip_test_check=True)
        time.sleep(0.1)
        assert meeting_state.whisper_thread is not None
        assert meeting_state.whisper_thread.is_alive()

        meeting_state.end_meeting()
