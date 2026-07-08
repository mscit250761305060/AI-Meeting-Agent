import logging
from collections import deque

logger = logging.getLogger(__name__)


class TranscriptMemory:

    def __init__(self, max_messages=100):

        self.max_messages = max_messages
        self.messages = deque(maxlen=max_messages)

        logger.info("Transcript Memory Initialized")

    def add(self, speaker, text):

        if not text.strip():
            return

        self.messages.append({
            "speaker": speaker,
            "text": text
        })

    def get_recent(self, count=10):

        return list(self.messages)[-count:]

    def get_full_conversation(self):

        return list(self.messages)

    def clear(self):

        self.messages.clear()

        logger.info("Transcript Memory Cleared")


transcript_memory = TranscriptMemory()