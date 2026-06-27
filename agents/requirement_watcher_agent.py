import json
from pathlib import Path

from services.transcript_watcher import (
    watch_transcript
)

from agents.local_requirement_agent import (
    extract_requirements_local
)

transcript_buffer = []


def process_new_line(text):

    global transcript_buffer

    transcript_buffer.append(text)

    full_transcript = "\n".join(
        transcript_buffer
    )

    print("\nAnalyzing Requirements...\n")

    requirements = extract_requirements_local(
        full_transcript
    )

    output_file = Path(
        "data/requirements.json"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            requirements,
            f,
            indent=4
        )

    print(
        "Requirements Updated"
    )


if __name__ == "__main__":

    watch_transcript(
        "data/live_transcript.txt",
        process_new_line
    )