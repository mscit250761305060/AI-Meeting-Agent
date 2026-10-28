import json
import logging
import threading
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Form, Request, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.models import User, SessionRecord, TranscriptChunk
from app.services.auth_service import get_optional_user
from app.services import meeting_state
from app.services.meeting_service import MeetingService
from app.services.project_service import ProjectGenerationService
from app.services.ai.meeting_summary_service import MeetingSummaryService
from app.models.schemas import MeetingStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meeting", tags=["meeting"])

DATA_DIR = Path("data")
TRANSCRIPT_FILE = DATA_DIR / "live_transcript.txt"
REQUIREMENTS_FILE = DATA_DIR / "requirements.json"

@router.post("/join")
async def join_meeting(
    request: Request,
    link: Optional[str] = Form(None),
    open_mode: Optional[str] = Form(None),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Accepts meeting link via Form data or JSON payload.
    Supports open_mode='same_window_tab' to reuse the user's active Chrome window/session.
    Binds the session and browser profile to the authenticated user.
    """
    if not link:
        try:
            body = await request.json()
            link = body.get("link")
            if not open_mode:
                open_mode = body.get("open_mode")
        except Exception:
            link = None

    if not link:
        return {"success": False, "message": "Missing meeting link"}

    user_id = current_user.id if current_user else None
    return MeetingService.join(link, user_id=user_id, open_mode=open_mode or "same_window_tab")

@router.post("/stop")
def stop_meeting(current_user: Optional[User] = Depends(get_optional_user)):
    """
    Stops the meeting recording session, releases browser and meeting resources,
    and finalizes the associated project using all available transcript chunks.
    Enforces user isolation so users cannot stop another user's meeting.
    """
    user_id = current_user.id if current_user else None
    res = MeetingService.stop(user_id=user_id)
    if not res.get("success", False) and "Cannot stop" in res.get("message", ""):
        raise HTTPException(status_code=403, detail=res["message"])
    return res

@router.post("/auth-browser")
def open_auth_browser(current_user: Optional[User] = Depends(get_optional_user)):
    """
    Opens the user-isolated browser profile in a visible Chrome window so the user
    can safely sign in with their own authorized Google credentials.
    """
    from app.services.meeting_browser_agent import browser_agent
    user_id = current_user.id if current_user else None
    return browser_agent.open_auth_window(user_id=user_id)

@router.post("/launch-cdp-browser")
def launch_cdp_browser(current_user: Optional[User] = Depends(get_optional_user)):
    """
    Launches Chrome with remote debugging on port 9222 pointing to http://127.0.0.1:8000/dashboard,
    allowing Playwright to attach directly to tabs in that window via CDP for automated joining.
    """
    from app.services.meeting_browser_agent import browser_agent
    user_id = current_user.id if current_user else None
    return browser_agent.launch_cdp_browser(user_id=user_id)

@router.post("/confirm-joined")
def confirm_meeting_joined(current_user: Optional[User] = Depends(get_optional_user)):
    """
    Allows user or client to confirm active in-call status when participating in a native browser tab session.
    """
    from app.services.meeting_browser_agent import browser_agent
    from app.services import meeting_state
    user_id = current_user.id if current_user else None
    if meeting_state.current_user_id and user_id and meeting_state.current_user_id != user_id:
        raise HTTPException(status_code=403, detail="Cannot modify another user's active meeting session.")
    return browser_agent.confirm_joined()

@router.post("/transcript-chunk")
async def submit_transcript_chunk(request: Request, text: Optional[str] = Form(None)):
    """
    Accepts an incremental transcript chunk, persists it against the active session,
    broadcasts updates via WebSocket, and triggers incremental project updates.
    """
    if not text:
        try:
            body = await request.json()
            text = body.get("text")
        except Exception:
            text = None

    if not text:
        return {"success": False, "message": "Missing transcript text."}

    return MeetingService.process_transcript_chunk(text)

@router.get("/status", response_model=MeetingStatusResponse)
def get_meeting_status(current_user: Optional[User] = Depends(get_optional_user)):
    """
    Returns the real-time meeting state, link, transcript, parsed requirements, and browser join status.
    Isolated per authenticated user so users do not see another user's live call.
    """
    user_id = current_user.id if current_user else None
    service_status = MeetingService.get_status(user_id=user_id)

    transcript = ""
    requirements = {}
    if service_status.get("running", False):
        if TRANSCRIPT_FILE.exists():
            transcript = TRANSCRIPT_FILE.read_text(encoding="utf-8")
        if REQUIREMENTS_FILE.exists():
            try:
                requirements = json.loads(REQUIREMENTS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

    return MeetingStatusResponse(
        session_id=service_status.get("session_id"),
        project_id=service_status.get("project_id"),
        running=service_status.get("running", False),
        link=service_status.get("link"),
        meeting_type=service_status.get("platform"),
        platform=service_status.get("platform"),
        join_status=service_status.get("join_status", "idle"),
        message=service_status.get("message", "Agent is idle."),
        in_meeting=service_status.get("in_meeting", False),
        requires_login=service_status.get("requires_login", False),
        waiting_for_host=service_status.get("waiting_for_host", False),
        mode=service_status.get("mode"),
        cdp_attached=service_status.get("cdp_attached", False),
        transcript=transcript,
        requirements=requirements
    )


@router.post("/summarize")
def summarize_meeting(
    payload: Optional[dict] = Body(default=None),
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Generates an AI/extractive meeting summary, key points, decisions, and action items.
    Accepts optional session_id or raw transcript text; defaults to current active session transcript.
    Strictly verifies multi-user ownership before accessing session records.
    """
    session_id = None
    transcript_text = ""

    if payload:
        session_id = payload.get("session_id")
        transcript_text = payload.get("transcript", "")

    if not session_id:
        session_id = meeting_state.current_session_id

    # Check session ownership if session_id is provided and saved in DB
    if session_id and db:
        session_rec = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
        if session_rec and session_rec.user_id:
            if not current_user or session_rec.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied: this meeting belongs to another user.")

    # If transcript not explicitly passed in payload, retrieve session-specific chunks from DB
    if not transcript_text:
        if session_id and db:
            chunks = db.query(TranscriptChunk).filter(TranscriptChunk.session_id == session_id).order_by(TranscriptChunk.created_at.asc()).all()
            if chunks:
                transcript_text = " ".join(c.text for c in chunks)

        # Fallback to in-memory cumulative transcript or live transcript file if active session
        if not transcript_text:
            if meeting_state.cumulative_transcript:
                transcript_text = meeting_state.cumulative_transcript
            elif TRANSCRIPT_FILE.exists():
                transcript_text = TRANSCRIPT_FILE.read_text(encoding="utf-8")

    if not transcript_text.strip():
        return {
            "success": False,
            "message": "No transcript data available to summarize.",
            "summary": None
        }

    res = MeetingSummaryService.generate_summary(transcript_text, session_id=session_id, db=db)
    return res


@router.get("/summary/{session_id}")
def get_session_summary(
    session_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Retrieve stored AI summary and action items for a given meeting session."""
    # Check authorization if session has an owner
    if db:
        session_rec = db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
        if session_rec and session_rec.user_id:
            if not current_user or session_rec.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied: this meeting belongs to another user.")

    summary = MeetingSummaryService.get_summary_for_session(session_id, db=db)
    if not summary:
        raise HTTPException(status_code=404, detail=f"No summary found for session '{session_id}'.")
    return {"success": True, "summary": summary}


@router.get("/history")
def get_meeting_history(
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """
    Returns meeting sessions and summaries.
    Enforces user isolation: authenticated users see only their sessions;
    guests see unassigned legacy sessions.
    """
    if db is None:
        return {"success": True, "meetings": []}

    query = db.query(SessionRecord)
    if current_user:
        query = query.filter(SessionRecord.user_id == current_user.id)
    else:
        query = query.filter(SessionRecord.user_id.is_(None))

    records = query.order_by(SessionRecord.created_at.desc()).limit(50).all()

    meetings = []
    for rec in records:
        summary_rec = MeetingSummaryService.get_summary_for_session(rec.session_id, db=db)
        meetings.append({
            "session_id": rec.session_id,
            "user_id": rec.user_id,
            "status": rec.status,
            "meeting_link": rec.meeting_link,
            "created_at": rec.created_at.isoformat() if rec.created_at else None,
            "has_summary": bool(summary_rec),
            "summary_preview": summary_rec.get("overview") if summary_rec else None
        })

    return {"success": True, "meetings": meetings}
