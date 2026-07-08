import json
from pathlib import Path

from agents.json_response_cleaner_agent import (
    clean_json_response
)


def overwrite_project_files(
    response,
    project_path
):

    response = clean_json_response(
        response
    )

    files = json.loads(
        response
    )

    project_path = Path(
        project_path
    )

    for filename, code in files.items():

        path = project_path / filename

        path.write_text(

            code,

            encoding="utf-8"

        )

        print(

            f"Updated: {filename}"

        )