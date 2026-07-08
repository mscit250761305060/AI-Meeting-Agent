import logging

from agents.requirement_memory import memory

logger = logging.getLogger(__name__)


class RequirementUpdateEngine:

    def process(self, action: str, requirement: str):

        requirement = requirement.strip()

        if not requirement:
            return

        if action == "ADD":

            memory.add(requirement)

            logger.info("Requirement Added : %s", requirement)

            return

        if action == "REMOVE":

            memory.remove(requirement)

            logger.info("Requirement Removed : %s", requirement)

            return

        if action == "UPDATE":

            logger.info("Requirement Update Requested : %s", requirement)

            # Step 12 માં અહીં actual update આવશે

            return


update_engine = RequirementUpdateEngine()