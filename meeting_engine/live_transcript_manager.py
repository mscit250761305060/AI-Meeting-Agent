import logging

from agents.live_requirement_detector import should_process
from agents.meeting_filter_agent import is_project_requirement
from agents.speaker_diarization_agent import speaker_agent
from agents.transcript_pipeline_agent import process_live_transcript
from meeting_engine.transcript_memory import transcript_memory
from meeting_engine.requirement_memory import requirement_memory
from agents.requirement_classifier import classify_requirement
from meeting_engine.conversation_context import conversation_context
from meeting_engine.duplicate_detector import duplicate_detector
from agents.requirement_change_detector import detect_action
from agents.requirement_update_engine import update_engine
from agents.requirement_planner import planner

logger = logging.getLogger(__name__)


class LiveTranscriptManager:

    def __init__(self):
        logger.info("Live Transcript Manager Initialized")

        self.current_transcript = ""
        self.history = []

    def process(self, audio_path: str, transcript: str):

        logger.info("Processing Transcript Pipeline")

        if not transcript.strip():
            logger.info("Empty Transcript")
            return

        self.history.append(transcript)

        transcript_memory.add(
            speaker="UNKNOWN",
            text=transcript
        )

        segments = speaker_agent.detect_speakers(audio_path)

        logger.info("Speaker Segments: %s", len(segments))

        if not is_project_requirement(transcript):
            logger.info("Non Project Conversation")
            return

        if not should_process(transcript):
            logger.info("Duplicate Requirement")
            return
        
        conversation_context.add(transcript)

        action = detect_action(transcript)

        update_engine.process(
            action,
            transcript
        )

        logger.info("Requirement Action : %s", action)
        
        category = classify_requirement(transcript)

        if duplicate_detector.is_duplicate(transcript):
            return

        requirement_memory.add_requirement(
            category,
            transcript
        )

        prompt = planner.build_prompt(
            conversation_context.get_context(),
            requirement_memory.get_all(),
            transcript
        )

        logger.info(prompt)

        process_live_transcript(transcript)


transcript_manager = LiveTranscriptManager()