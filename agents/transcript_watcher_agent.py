import time
import threading
from pathlib import Path

from agents.gemini_requirement_agent import (
    extract_requirements_ai
)


TRANSCRIPT = Path(
    "data/live_transcript.txt"
)

OUTPUT = Path(
    "data/requirements.json"
)


def start_transcript_watcher():

    last_text = ""

    print(
        "Transcript Watcher Started..."
    )

    while True:

        if TRANSCRIPT.exists():

            text = TRANSCRIPT.read_text(
                encoding="utf-8"
            )

            if (
                text.strip()
                and text != last_text
            ):

                requirements = (
                    extract_requirements_ai(
                        text
                    )
                )

                OUTPUT.write_text(

                    __import__("json").dumps(

                        requirements,

                        indent=4

                    ),

                    encoding="utf-8"

                )

                print(

                    "Requirements Updated"

                )

                text = text.strip()

                if text == last_text:
                    continue

                last_text = text

        time.sleep(2)