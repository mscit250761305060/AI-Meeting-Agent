import json
from pathlib import Path

from agents.local_requirement_agent import (
    extract_requirements_local
)


def update_requirements(new_text):

    print("\nAnalyzing Requirements...")

    transcript_file = Path(
        "data/live_transcript.txt"
    )

    new_text = transcript_file.read_text(
        encoding="utf-8"
    )

    try:

        # requirements = extract_requirements(
        #     # full_transcript
        #     new_text
        # )
        requirements = extract_requirements_local(
            new_text
        )

        if "error" in requirements:

            print(
                f"Skipping update: {requirements['error']}"
            )

            return


    except Exception as e:

        print(
            f"Gemini Error: {e}"
        )

        return

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

    print("Requirements Updated")