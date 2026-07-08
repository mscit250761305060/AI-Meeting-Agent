from agents.requirement_hash_agent import (
    get_hash
)

from meeting_engine.live_buffer import (
    meeting_buffer
)


def should_process(text):

    key = get_hash(text)

    if key in meeting_buffer:

        return False

    meeting_buffer.append(key)

    if len(meeting_buffer) > 50:

        meeting_buffer.pop(0)

    return True