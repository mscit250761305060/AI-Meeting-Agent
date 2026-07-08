import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class RequirementMemory:

    def __init__(self):

        self.requirements = defaultdict(list)

        logger.info("Requirement Memory Initialized")

    def add_requirement(self, category, requirement):

        if not requirement.strip():
            return

        if requirement not in self.requirements[category]:
            self.requirements[category].append(requirement)

            logger.info(
                "Requirement Added [%s] : %s",
                category,
                requirement
            )

    def get_category(self, category):

        return self.requirements.get(category, [])

    def get_all(self):

        return dict(self.requirements)

    def clear(self):

        self.requirements.clear()

        logger.info("Requirement Memory Cleared")


requirement_memory = RequirementMemory()