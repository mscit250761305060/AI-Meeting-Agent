import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class SpeakerSegment:
    speaker: str
    start: float
    end: float
    text: str = ""


class SpeakerDiarizationAgent:

    def __init__(self):
        logger.info("Speaker Diarization Agent Initialized")

    def detect_speakers(self, audio_path: str) -> List[SpeakerSegment]:
        """
        Placeholder.

        Future:
        - pyannote.audio
        - NVIDIA NeMo
        - WhisperX

        Returns list of speaker segments.
        """

        logger.info("Speaker Detection Started : %s", audio_path)

        return [
            SpeakerSegment(
                speaker="UNKNOWN",
                start=0.0,
                end=0.0,
                text=""
            )
        ]


speaker_agent = SpeakerDiarizationAgent()