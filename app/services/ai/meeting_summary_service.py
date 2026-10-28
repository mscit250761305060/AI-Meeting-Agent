import re
import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.database.database import SessionLocal
from app.models.models import MeetingSummary, SessionRecord, TranscriptChunk
from app.services.ai.ollama_service import ollama_service

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class MeetingSummaryService:
    """
    Intelligent meeting summarization service.
    Extracts executive overview, key discussion points, decisions, and action items.
    Rely on local Ollama when available, with resilient extractive fallback.
    """

    @classmethod
    def generate_summary(cls, transcript_text: Optional[str] = None, session_id: Optional[str] = None, db: Optional[Session] = None) -> Dict[str, Any]:
        cleaned_text = (transcript_text or "").strip()
        words = cleaned_text.split()
        if len(words) < 5:
            return {
                "success": False,
                "message": "Transcript is too brief to generate a meaningful summary.",
                "summary": None
            }

        summary_data = None
        provider_used = "extractive"

        # 1. Attempt generation via Ollama if available
        if ollama_service.is_available():
            try:
                summary_data = cls._generate_with_ollama(cleaned_text)
                if summary_data:
                    provider_used = "ollama"
            except Exception as exc:
                logger.warning(f"Ollama summarization encountered error: {exc}. Falling back to extractive engine.")

        # 2. Resilient fallback to structured extractive analysis
        if not summary_data:
            summary_data = cls._generate_extractive_summary(cleaned_text)

        # 3. Persist summary into database if session_id is provided
        if session_id:
            try:
                def _persist(db_sess):
                    existing_summary = db_sess.query(MeetingSummary).filter(MeetingSummary.session_id == session_id).first()
                    if existing_summary:
                        existing_summary.summary_text = summary_data.get("overview", "")
                        existing_summary.key_points = summary_data.get("key_points", [])
                        existing_summary.action_items = summary_data.get("action_items", [])
                        existing_summary.decisions = summary_data.get("decisions", [])
                    else:
                        new_summary = MeetingSummary(
                            id=str(uuid.uuid4()),
                            session_id=session_id,
                            summary_text=summary_data.get("overview", ""),
                            key_points=summary_data.get("key_points", []),
                            action_items=summary_data.get("action_items", []),
                            decisions=summary_data.get("decisions", [])
                        )
                        db_sess.add(new_summary)
                    db_sess.commit()

                if db is not None:
                    _persist(db)
                elif SessionLocal:
                    with SessionLocal() as db_sess:
                        _persist(db_sess)
            except Exception as e:
                logger.warning(f"Could not persist meeting summary to database: {e}")

        summary_data["provider"] = provider_used
        return {
            "success": True,
            "session_id": session_id,
            "summary": summary_data
        }

    @classmethod
    def _generate_with_ollama(cls, text: str) -> Optional[Dict[str, Any]]:
        prompt = (
            "You are an expert executive meeting assistant. Analyze this transcript and return valid JSON only.\n"
            "CRITICAL: Base all key points, decisions, and action items strictly and only on the provided transcript text. "
            "Do not invent, assume, or hallucinate information not present in the transcript.\n\n"
            "{\n"
            '  "overview": "Clear 2-3 sentence executive summary of the meeting goals and discussion",\n'
            '  "key_points": ["Key point 1", "Key point 2", ...],\n'
            '  "decisions": ["Decision 1", "Decision 2", ...],\n'
            '  "action_items": [{"task": "description", "owner": "name or unassigned", "priority": "High|Medium|Low"}]\n'
            "}\n\n"
            f"TRANSCRIPT:\n{text}"
        )
        response_text = ollama_service.generate(
            prompt=prompt,
            json_mode=True,
            temperature=0.2
        )
        if not response_text:
            return None

        # Parse JSON output
        parsed = None
        try:
            parsed = json.loads(response_text)
        except Exception:
            # Try to locate JSON inside markdown block
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except Exception:
                    pass

        if isinstance(parsed, dict):
            parsed.setdefault("overview", "Meeting discussion summary.")
            parsed.setdefault("key_points", [])
            parsed.setdefault("decisions", [])
            parsed.setdefault("action_items", [])
            return parsed

        return None

    @classmethod
    def _generate_extractive_summary(cls, text: str) -> Dict[str, Any]:
        """
        Extractive rule-based meeting analysis.
        Extracts action items, decisions, and key statements safely without external API dependencies.
        Strictly relies only on actual spoken transcript text.
        """
        lines = [line.strip() for line in re.split(r"[\n.]+", text) if line.strip()]

        key_points = []
        decisions = []
        action_items = []

        action_triggers = ["need to", "must", "should", "will create", "will build", "will implement", "action item", "todo", "assign", "follow up"]
        decision_triggers = ["agreed", "decided", "decision", "approved", "chosen", "consensus", "settled on", "we will use", "will use"]

        PRONOUNS = {"we", "i", "they", "you", "it", "there", "this", "that", "the", "he", "she"}
        for line in lines:
            line_lower = line.lower()
            owner_match = re.search(r"\b([A-Z][a-z]+)\s+(will|should|must|needs to)\b", line)
            if owner_match and owner_match.group(1).lower() in PRONOUNS:
                owner_match = None

            is_action = any(trig in line_lower for trig in action_triggers) or (owner_match is not None)

            if any(trig in line_lower for trig in decision_triggers):
                decisions.append(line)
            elif is_action:
                owner = owner_match.group(1) if owner_match else "Team"
                action_items.append({
                    "task": line,
                    "owner": owner,
                    "priority": "High" if ("urgent" in line_lower or "must" in line_lower or "immediately" in line_lower) else "Medium"
                })
            elif len(line.split()) >= 4 and len(key_points) < 6:
                key_points.append(line)

        # Overview synthesis
        if lines:
            first_few = ". ".join(lines[:min(3, len(lines))])
            overview = f"Meeting discussion summary: {first_few}."
        else:
            overview = "Meeting session recorded."

        return {
            "overview": overview,
            "key_points": key_points if key_points else ["Meeting discussion recorded."],
            "decisions": decisions if decisions else ["Discussion ongoing; no explicit decisions recorded."],
            "action_items": action_items if action_items else []
        }

    @classmethod
    def get_summary_for_session(cls, session_id: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
        """Retrieve stored summary for a meeting session."""
        def _get(db_sess):
            summary = db_sess.query(MeetingSummary).filter(MeetingSummary.session_id == session_id).first()
            if not summary:
                return None
            return {
                "session_id": summary.session_id,
                "overview": summary.summary_text,
                "key_points": summary.key_points or [],
                "action_items": summary.action_items or [],
                "decisions": summary.decisions or [],
                "created_at": summary.created_at.isoformat() if summary.created_at else None
            }

        if db is not None:
            return _get(db)
        if not SessionLocal:
            return None
        with SessionLocal() as db_sess:
            return _get(db_sess)
