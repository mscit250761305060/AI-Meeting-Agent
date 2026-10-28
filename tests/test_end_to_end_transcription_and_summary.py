import os
import tempfile
import wave
import pytest
from unittest.mock import patch, MagicMock

from tests.conftest import TestingSessionLocal
from app.models.models import SessionRecord, TranscriptChunk, MeetingSummary
from app.services import meeting_state
from app.services.meeting_service import MeetingService
from app.services.ai.meeting_summary_service import MeetingSummaryService
from meeting_engine.whisper_worker import transcribe_audio


@pytest.fixture(autouse=True)
def clean_state():
    meeting_state.reset_runtime_state()
    yield
    meeting_state.reset_runtime_state()


def test_missing_audio_file_returns_empty_safely():
    """Verify that a missing or non-existent audio file does not crash and returns empty text."""
    res = transcribe_audio("non_existent_audio_path_12345.wav")
    assert res == ""


def test_real_audio_transcription_from_wav_file():
    """
    Verify speech-to-text using Faster-Whisper on an actual wav file.
    Tests meeting_audio.wav which contains spoken speech.
    """
    if not os.path.exists("meeting_audio.wav"):
        pytest.skip("meeting_audio.wav not found in root")

    transcript = transcribe_audio("meeting_audio.wav")
    assert isinstance(transcript, str)
    assert len(transcript.strip()) > 0


def test_transcript_chunk_storage_db_memory_and_file(tmp_path):
    """
    Verify that when a transcript chunk arrives, it is correctly:
    1. Persisted as a TranscriptChunk in the database.
    2. Appended to meeting_state.cumulative_transcript.
    3. Written to data/live_transcript.txt.
    """
    import uuid
    session_id = f"session_storage_{uuid.uuid4().hex[:8]}"
    meeting_state.begin_meeting(session_id)

    chunk1 = "The team agreed to adopt OAuth2 with Google authentication."
    chunk2 = "Sarah will implement the auth callback endpoint by Thursday."

    res1 = MeetingService.process_transcript_chunk(chunk1, session_id=session_id)
    assert res1["success"] is True

    res2 = MeetingService.process_transcript_chunk(chunk2, session_id=session_id)
    assert res2["success"] is True

    # 1. In-memory cumulative check
    assert chunk1 in meeting_state.cumulative_transcript
    assert chunk2 in meeting_state.cumulative_transcript

    # 2. File check
    live_txt_path = os.path.join("data", "live_transcript.txt")
    assert os.path.exists(live_txt_path)
    with open(live_txt_path, "r", encoding="utf-8") as f:
        file_content = f.read()
    assert chunk1 in file_content
    assert chunk2 in file_content

    # 3. Database check via SessionLocal (used by background MeetingService)
    from app.database.database import SessionLocal
    with SessionLocal() as db:
        chunks = db.query(TranscriptChunk).filter(TranscriptChunk.session_id == session_id).order_by(TranscriptChunk.created_at.asc()).all()
        assert len(chunks) == 2
        assert chunks[0].text == chunk1
        assert chunks[1].text == chunk2


def test_ai_summary_key_points_decisions_and_actions_strictly_grounded():
    """
    Verify that the AI summary extracts overview, key points, decisions, and action items
    strictly derived from the transcript, assigning owners and priorities accurately.
    """
    session_id = "test_summary_grounded_session"
    transcript = (
        "We reviewed the Q3 cloud infrastructure budget today. "
        "The team agreed to migrate the analytics database to BigQuery. "
        "We decided to deprecate legacy v1 REST endpoints next month. "
        "David must configure the IAM roles with least privilege by Friday. "
        "Elena should prepare the data pipeline migration script. "
        "We will use terraform for infrastructure as code."
    )

    with TestingSessionLocal() as db:
        res = MeetingSummaryService.generate_summary(transcript, session_id=session_id, db=db)
        assert res["success"] is True
        summary = res["summary"]

        # Overview
        assert "overview" in summary
        assert len(summary["overview"]) > 0

        # Decisions
        decisions = summary.get("decisions", [])
        assert any("BigQuery" in d for d in decisions)
        assert any("deprecate" in d or "legacy" in d for d in decisions)
        assert any("terraform" in d for d in decisions)

        # Action items
        action_items = summary.get("action_items", [])
        assert len(action_items) >= 2

        # Check David's task
        david_action = next((a for a in action_items if a.get("owner") == "David"), None)
        assert david_action is not None
        assert "IAM roles" in david_action["task"]
        assert david_action["priority"] == "High"  # 'must' implies High priority

        # Check Elena's task
        elena_action = next((a for a in action_items if a.get("owner") == "Elena"), None)
        assert elena_action is not None
        assert "migration script" in elena_action["task"]

        # Verify DB persistence
        db_summary = MeetingSummaryService.get_summary_for_session(session_id, db=db)
        assert db_summary is not None
        assert db_summary["session_id"] == session_id
        assert len(db_summary["decisions"]) >= 2
        assert len(db_summary["action_items"]) >= 2


def test_error_handling_empty_or_too_short_transcripts():
    """Verify error handling for empty, whitespace, null, or excessively short transcripts."""
    with TestingSessionLocal() as db:
        # None
        res_none = MeetingSummaryService.generate_summary(None, db=db)
        assert res_none["success"] is False
        assert "too brief" in res_none["message"].lower()

        # Empty string
        res_empty = MeetingSummaryService.generate_summary("", db=db)
        assert res_empty["success"] is False
        assert "too brief" in res_empty["message"].lower()

        # Whitespace
        res_space = MeetingSummaryService.generate_summary("   \n\t  ", db=db)
        assert res_space["success"] is False

        # Only 2 words
        res_short = MeetingSummaryService.generate_summary("Meeting ended.", db=db)
        assert res_short["success"] is False
        assert "too brief" in res_short["message"].lower()


def test_error_handling_unavailable_ai_provider_falls_back_resiliently():
    """
    Verify that when local Ollama (or other external AI providers) are unreachable or error out,
    the service catches the failure, logs a warning, and returns a valid structured extractive summary.
    """
    transcript = (
        "We decided to release the beta version next Monday. "
        "Alice will deploy the staging environment by tomorrow afternoon."
    )

    # Mock ollama_service.is_available() as False to simulate offline provider
    with patch("app.services.ai.meeting_summary_service.ollama_service.is_available", return_value=False):
        res = MeetingSummaryService.generate_summary(transcript)
        assert res["success"] is True
        assert res["summary"]["provider"] == "extractive"
        assert len(res["summary"]["decisions"]) > 0
        assert len(res["summary"]["action_items"]) > 0

    # Mock ollama_service raising a connection/timeout exception
    with patch("app.services.ai.meeting_summary_service.ollama_service.is_available", return_value=True), \
         patch("app.services.ai.meeting_summary_service.ollama_service.generate", side_effect=Exception("Connection refused: 11434")):
        res = MeetingSummaryService.generate_summary(transcript)
        assert res["success"] is True
        assert res["summary"]["provider"] == "extractive"
        assert len(res["summary"]["decisions"]) > 0
        assert len(res["summary"]["action_items"]) > 0


def test_session_specific_transcript_retrieval_for_past_meetings(client=None):
    """
    Verify that /meeting/summarize correctly retrieves chunks for the requested past session_id
    from the database, without corrupting or leaking the current live transcript file.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    test_client = TestClient(app)

    session_past = "session_historical_101"
    session_current = "session_live_202"

    with TestingSessionLocal() as db:
        # Create records for historical session
        db.add(SessionRecord(session_id=session_past, status="completed", meeting_link="https://meet.google.com/past-meet"))
        db.add(TranscriptChunk(id="chunk_past_1", session_id=session_past, text="We decided on the blue theme for the website. Mark will prepare the CSS palette."))
        db.commit()

    # Set current live session in memory
    meeting_state.current_session_id = session_current
    meeting_state.cumulative_transcript = "Unrelated live meeting about quarterly sales numbers."

    # Request summary specifically for past session
    response = test_client.post("/meeting/summarize", json={"session_id": session_past})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    summary = data["summary"]

    # Must contain the historical decision/action, NOT the live sales numbers
    assert any("blue theme" in d for d in summary["decisions"])
    assert any("Mark" in a.get("owner", "") for a in summary["action_items"])
    assert "sales numbers" not in summary["overview"]
