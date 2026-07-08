from agents.meeting_listener_agent import (
    append_transcript
)


def receive_transcript(text):

    if not text:
        return

    text = text.strip()

    if text:

        append_transcript(text)

        print(f"Transcript: {text}")