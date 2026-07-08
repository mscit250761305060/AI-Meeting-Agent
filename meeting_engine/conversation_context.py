import logging
from collections import deque

logger = logging.getLogger(__name__)


class ConversationContext:

    def __init__(self, max_history=30):

        self.history = deque(maxlen=max_history)

        logger.info("Conversation Context Initialized")

    def add(self, text):

        if text.strip():

            self.history.append(text)

    def get_context(self):

        return "\n".join(self.history)

    def get_last(self, count=5):

        return list(self.history)[-count:]

    def clear(self):

        self.history.clear()

        logger.info("Conversation Context Cleared")


conversation_context = ConversationContext()