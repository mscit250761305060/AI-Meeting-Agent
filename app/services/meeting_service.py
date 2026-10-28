import logging
import threading
from typing import Optional, Dict, Any
from app.services import meeting_state
from app.services.meeting_browser_agent import browser_agent, validate_and_classify_url, JoinStatus, MeetingPlatform

logger = logging.getLogger(__name__)

class MeetingService:
    @staticmethod
    def _run_meeting_lifecycle():
        try:
            meeting_state.start_runtime()
            while meeting_state.meeting_running and not meeting_state.stop_event.is_set():
                if not browser_agent.is_worker_alive():
                    b_status = browser_agent.status
                    if b_status in (JoinStatus.FAILED, JoinStatus.ADMISSION_DENIED, JoinStatus.STOPPED):
                        meeting_state.end_meeting(
                            final_status=b_status.value,
                            final_message=browser_agent.message
                        )
                        break
                meeting_state.stop_event.wait(0.5)
        except Exception as exc:
            logger.exception("Meeting lifecycle interrupted: %s", exc)
        finally:
            if meeting_state.meeting_running and meeting_state.stop_event.is_set():
                meeting_state.end_meeting()

    @classmethod
    def join(cls, link: str, participant_name: str = "AI Meeting Agent", user_id: Optional[str] = None, open_mode: Optional[str] = None) -> dict:
        if not link:
            return {"success": False, "status": "failed", "message": "Missing meeting link"}

        # 1. Validate and classify meeting link
        is_valid, platform, msg_or_norm = validate_and_classify_url(link)
        if not is_valid:
            return {
                "success": False,
                "status": "failed",
                "platform": platform.value,
                "message": msg_or_norm
            }

        meeting_state.meeting_link = msg_or_norm
        meeting_state.meeting_type = platform.value
        meeting_state.platform = platform.value

        # Check if an active meeting browser worker is running
        if meeting_state.meeting_running:
            if browser_agent.is_worker_alive():
                if meeting_state.current_user_id and user_id and meeting_state.current_user_id != user_id:
                    return {
                        "success": False,
                        "status": "failed",
                        "platform": meeting_state.platform,
                        "message": "Another meeting session is currently active. Please wait or stop the existing session.",
                        "link": None,
                        "session_id": None,
                    }
                agent_status = browser_agent.get_status_dict()
                return {
                    "success": agent_status.get("in_meeting", False) or agent_status.get("join_status") in (
                        JoinStatus.REQUEST_SENT.value,
                        JoinStatus.WAITING_ADMISSION.value,
                        JoinStatus.LOGIN_REQUIRED.value,
                        JoinStatus.MANUAL_ACTION_REQUIRED.value,
                        JoinStatus.JOINING.value,
                        JoinStatus.NAVIGATING.value,
                        JoinStatus.LAUNCHING_BROWSER.value,
                    ),
                    "status": agent_status.get("join_status", "idle"),
                    "platform": meeting_state.platform,
                    "mode": agent_status.get("open_mode"),
                    "cdp_attached": agent_status.get("cdp_attached", False),
                    "message": agent_status.get("message", "Meeting session in progress."),
                    "link": meeting_state.meeting_link,
                    "session_id": meeting_state.current_session_id,
                }
            else:
                # Previous session is stale or browser worker has stopped/exited: clean up stale state
                meeting_state.end_meeting()

        if not meeting_state.begin_meeting(user_id=user_id):
            return {"success": False, "status": "failed", "message": "Failed to begin meeting state"}

        # 2. Persist session to database safely
        session_id = meeting_state.current_session_id
        try:
            from app.database.database import SessionLocal
            from app.models.models import SessionRecord
            if SessionLocal:
                with SessionLocal() as db:
                    session_rec = SessionRecord(
                        session_id=session_id,
                        user_id=user_id,
                        status="active",
                        meeting_link=msg_or_norm
                    )
                    db.add(session_rec)
                    db.commit()
        except Exception as e:
            logger.warning(f"Could not persist session to DB: {e}")

        # 3. Launch automated browser session or attach in-tab session
        effective_mode = open_mode or "same_window_tab"
        join_res = browser_agent.start_join(msg_or_norm, user_id=user_id, open_mode=effective_mode)

        if not join_res.get("success", False):
            # Clean up meeting_state so it is never stuck in running state
            meeting_state.end_meeting(
                final_status=join_res.get("status", JoinStatus.FAILED.value),
                final_message=join_res.get("message", "Browser launch failed.")
            )
            return {
                "success": False,
                "status": join_res.get("status", JoinStatus.FAILED.value),
                "platform": platform.value,
                "message": join_res.get("message", "Browser launch failed."),
                "link": msg_or_norm,
                "session_id": session_id,
            }

        # Start lifecycle monitor thread
        lifecycle_thread = threading.Thread(
            target=cls._run_meeting_lifecycle,
            name="meeting-lifecycle",
            daemon=True,
        )
        lifecycle_thread.start()

        return {
            "success": True,
            "status": join_res.get("status", JoinStatus.LAUNCHING_BROWSER.value),
            "platform": platform.value,
            "mode": join_res.get("mode", "browser"),
            "cdp_attached": join_res.get("cdp_attached", False),
            "message": join_res.get("message", "Browser join initiated."),
            "link": msg_or_norm,
            "session_id": session_id,
        }

    @classmethod
    def process_transcript_chunk(cls, chunk_text: str, session_id: Optional[str] = None) -> dict:
        """
        Incrementally captures discussion transcript chunks, stores them against the session
        in the database, broadcasts via WebSocket, and triggers incremental project synthesis
        only when requirements meaningfully change.
        """
        import uuid
        from pathlib import Path
        from app.services.ws_manager import manager
        from app.services.project_service import ProjectGenerationService
        from app.services.generator.requirement_parser import parse_requirements

        if not chunk_text or not chunk_text.strip():
            return {"success": False, "message": "Empty transcript chunk."}

        clean_chunk = chunk_text.strip()
        active_session_id = session_id or meeting_state.current_session_id or f"session_{uuid.uuid4().hex[:12]}"

        # 1. Store chunk in database
        chunk_id = str(uuid.uuid4())
        try:
            from app.database.database import SessionLocal
            from app.models.models import TranscriptChunk, SessionRecord
            if SessionLocal:
                with SessionLocal() as db:
                    sess = db.query(SessionRecord).filter(SessionRecord.session_id == active_session_id).first()
                    if not sess:
                        sess = SessionRecord(session_id=active_session_id, status="active", meeting_link=meeting_state.meeting_link)
                        db.add(sess)
                        db.flush()

                    db_chunk = TranscriptChunk(
                        id=chunk_id,
                        session_id=active_session_id,
                        text=clean_chunk
                    )
                    db.add(db_chunk)
                    db.commit()
        except Exception as e:
            logger.warning(f"Could not persist TranscriptChunk to database: {e}")

        # 2. Append to cumulative transcript
        if meeting_state.cumulative_transcript:
            meeting_state.cumulative_transcript += " " + clean_chunk
        else:
            meeting_state.cumulative_transcript = clean_chunk

        # Write to data/live_transcript.txt
        data_dir = Path("data")
        data_dir.mkdir(exist_ok=True)
        (data_dir / "live_transcript.txt").write_text(meeting_state.cumulative_transcript, encoding="utf-8")

        # 3. Broadcast status and transcript updates through existing WebSocket
        manager.broadcast_sync({
            "action": "transcript_update",
            "text": meeting_state.cumulative_transcript,
            "session_id": active_session_id,
        })
        manager.broadcast_sync({
            "action": "log",
            "message": f"Captured chunk: \"{clean_chunk[:80]}{'...' if len(clean_chunk) > 80 else ''}\"",
            "type": "i"
        })

        # 4. Incremental requirement parsing
        try:
            spec = parse_requirements(meeting_state.cumulative_transcript)
        except Exception as exc:
            logger.warning("Could not parse requirements from current transcript: %s", exc)
            return {"success": True, "message": "Transcript saved; parsing pending more context.", "chunk_id": chunk_id}

        # Check if specification has changed meaningfully to avoid unnecessary complete rebuilds
        spec_digest = (
            spec.project_name,
            spec.entity_name,
            tuple(sorted(spec.features)),
            tuple(sorted(p.title for p in spec.pages)),
            tuple(sorted((f.name, f.type) for f in spec.fields))
        )

        if spec_digest != meeting_state.last_spec_hash:
            meeting_state.last_spec_hash = spec_digest
            manager.broadcast_sync({
                "action": "requirements",
                "data": spec.model_dump()
            })
            # Incrementally synthesize and persist
            synth_res = ProjectGenerationService._execute_synthesis_pipeline(spec, session_id=active_session_id)
            return {
                "success": True,
                "message": "Transcript captured and project incrementally updated.",
                "chunk_id": chunk_id,
                "project_updated": True,
                "project_name": spec.project_name,
                "synthesis": synth_res
            }

        return {
            "success": True,
            "message": "Transcript captured. Requirements unchanged.",
            "chunk_id": chunk_id,
            "project_updated": False
        }

    @classmethod
    def get_status(cls, user_id: Optional[str] = None) -> dict:
        # If active meeting belongs to a different user, return idle status to preserve user isolation
        if meeting_state.current_user_id and user_id and meeting_state.current_user_id != user_id:
            return {
                "session_id": None,
                "running": False,
                "link": None,
                "platform": None,
                "join_status": "idle",
                "message": "Agent is idle.",
                "in_meeting": False,
                "requires_login": False,
                "waiting_for_host": False,
                "project_id": None,
            }

        agent_status = browser_agent.get_status_dict()
        join_stat = agent_status.get("join_status", "idle")
        if join_stat == "idle" and meeting_state.join_status and meeting_state.join_status != "idle":
            join_stat = meeting_state.join_status
        msg = agent_status.get("message", "Agent is idle.")
        if msg == "Agent is idle." and meeting_state.join_message and meeting_state.join_message != "Agent is idle.":
            msg = meeting_state.join_message

        return {
            "session_id": meeting_state.current_session_id,
            "running": meeting_state.meeting_running,
            "link": meeting_state.meeting_link,
            "platform": meeting_state.platform or meeting_state.meeting_type,
            "join_status": join_stat,
            "message": msg,
            "in_meeting": agent_status.get("in_meeting", False),
            "requires_login": agent_status.get("requires_login", False),
            "waiting_for_host": agent_status.get("waiting_for_host", False),
            "mode": agent_status.get("open_mode"),
            "cdp_attached": agent_status.get("cdp_attached", False),
            "project_id": meeting_state.current_project_id,
        }

    @classmethod
    def stop(cls, user_id: Optional[str] = None) -> dict:
        from pathlib import Path
        from app.services.project_service import ProjectGenerationService

        if meeting_state.current_user_id and user_id and meeting_state.current_user_id != user_id:
            return {"success": False, "message": "Cannot stop another user's active meeting session."}

        active_session_id = meeting_state.current_session_id
        browser_res = browser_agent.stop()
        if not meeting_state.end_meeting():
            return {"success": False, "message": "Meeting already stopped"}

        # Update session status in DB
        try:
            from app.database.database import SessionLocal
            from app.models.models import SessionRecord
            if SessionLocal:
                with SessionLocal() as db:
                    if active_session_id:
                        sess = db.query(SessionRecord).filter(SessionRecord.session_id == active_session_id).first()
                        if sess:
                            sess.status = "completed"
                    active = db.query(SessionRecord).filter(SessionRecord.status == "active").all()
                    for s in active:
                        s.status = "completed"
                    db.commit()
        except Exception as e:
            logger.warning(f"Could not update session status in DB: {e}")

        # Finalize project using all available transcript chunks and extracted requirements
        full_transcript = meeting_state.cumulative_transcript
        if not full_transcript.strip():
            transcript_file = Path("data/live_transcript.txt")
            if transcript_file.exists():
                full_transcript = transcript_file.read_text(encoding="utf-8")

        if full_transcript.strip():
            gen_res = ProjectGenerationService.generate_demo_from_transcript(
                full_transcript,
                session_id=active_session_id
            )
            details = gen_res.get("details", {})
            return {
                "success": gen_res.get("success", False),
                "message": "Meeting stopped and project finalized successfully." if gen_res.get("success") else gen_res.get("message"),
                "session_id": active_session_id,
                "project_id": details.get("project_id"),
                "project_name": details.get("project_name"),
                "project_path": details.get("project_path"),
                "running_url": gen_res.get("running_url"),
                "validation": details.get("validation"),
                "unsupported_features": details.get("unsupported", []),
                "browser_status": browser_res.get("message", "")
            }

        return {
            "success": True,
            "message": "Meeting stopped and browser session closed. No transcript captured.",
            "session_id": active_session_id,
            "browser_status": browser_res.get("message", "")
        }
