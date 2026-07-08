import threading


class RequirementMemory:

    def __init__(self):
        self.lock = threading.Lock()
        self.requirements = []

    def add(self, requirement: str):

        requirement = requirement.strip()

        if not requirement:
            return

        with self.lock:

            if requirement not in self.requirements:
                self.requirements.append(requirement)

    def remove(self, requirement: str):

        with self.lock:

            if requirement in self.requirements:
                self.requirements.remove(requirement)

    def all(self):

        with self.lock:
            return self.requirements.copy()

    def clear(self):

        with self.lock:
            self.requirements.clear()


memory = RequirementMemory()