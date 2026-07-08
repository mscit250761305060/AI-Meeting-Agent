import logging

logger = logging.getLogger(__name__)


class RequirementPlanner:

    def __init__(self):
        logger.info("Requirement Planner Initialized")

    def build_prompt(
        self,
        conversation_context,
        requirement_memory,
        latest_message
    ):

        prompt = f"""
You are an Expert Software Business Analyst.

Conversation History:

{conversation_context}

---------------------------------

Current Requirement Memory:

{requirement_memory}

---------------------------------

Latest Client Message:

{latest_message}

---------------------------------

Your Job

1. Understand latest client message.

2. Decide

ADD

REMOVE

UPDATE

NO CHANGE

3. Return updated structured requirement list.

Return JSON only.
"""

        return prompt


planner = RequirementPlanner()