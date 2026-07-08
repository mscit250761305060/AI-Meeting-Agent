import json
from pathlib import Path

from agents.json_response_cleaner_agent import (
    clean_json_response
)


def write_generated_files(
    response,
    output_folder
):

    response = clean_json_response(
        response
    )

    files = json.loads(response)

    output_folder = Path(output_folder)

    for filename, content in files.items():

        path = output_folder / filename

        path.write_text(
            content,
            encoding="utf-8"
        )

        print(
            f"Generated: {filename}"
        )