import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class DuplicateDetector:

    def __init__(self):
        self.requirements = []

    def is_duplicate(self, text, threshold=0.90):

        text = text.strip().lower()

        for old in self.requirements:

            score = SequenceMatcher(
                None,
                text,
                old
            ).ratio()

            if score >= threshold:
                logger.info("Duplicate Requirement Detected")
                return True

        self.requirements.append(text)

        return False

    def clear(self):
        self.requirements.clear()


duplicate_detector = DuplicateDetector()