import json
from pathlib import Path

from agents.gemini_requirement_agent import (
    extract_requirements_ai
)

from agents.project_regenerator_agent import (
    start_project_regenerator
)


OUTPUT = Path(
    "data/requirements.json"
)


def update_requirements(transcript):

    requirements = extract_requirements_ai(
        transcript
    )

    OUTPUT.write_text(

        json.dumps(

            requirements,

            indent=4

        ),

        encoding="utf-8"

    )

    print(

        "Requirements Updated"

    )

    # Trigger regeneration pipeline
    start_project_regenerator()

    return requirements