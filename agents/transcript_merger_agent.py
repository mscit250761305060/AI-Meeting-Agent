from agents.meeting_context_agent import (
    get_context
)


def merge_transcript(new_text):

    context = get_context().strip()

    if not context:

        return new_text.strip()

    return context + "\n" + new_text.strip()