import json
from pathlib import Path


LAST_REQUIREMENTS = Path(
    "data/last_requirements.json"
)


def get_requirement_changes(current):

    if not LAST_REQUIREMENTS.exists():

        LAST_REQUIREMENTS.write_text(

            json.dumps(
                current,
                indent=4
            ),

            encoding="utf-8"

        )

        return current

    previous = json.loads(

        LAST_REQUIREMENTS.read_text(
            encoding="utf-8"
        )

    )

    changes = {}

    for key, value in current.items():

        if previous.get(key) != value:

            changes[key] = value

    LAST_REQUIREMENTS.write_text(

        json.dumps(
            current,
            indent=4
        ),

        encoding="utf-8"

    )

    return changes