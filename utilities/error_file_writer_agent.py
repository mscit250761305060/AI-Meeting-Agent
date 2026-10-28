import json
from pathlib import Path

from utilities.json_response_cleaner_agent import (
    clean_json_response
)

FRONTEND_EXTENSIONS = {".html", ".css", ".js"}
BACKEND_FILENAMES = {"app.py", "database.py", "models.py", "schemas.py", "crud.py"}


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

    backend_path = project_path / "backend"
    frontend_path = project_path / "frontend"

    for filename, code in files.items():
        ext = Path(filename).suffix.lower()
        basename = Path(filename).name

        # Route to the correct subfolder if it exists
        is_backend_file = basename in BACKEND_FILENAMES or filename.startswith("api/") or filename.startswith("backend/")
        
        if backend_path.exists() and is_backend_file:
            if filename.startswith("backend/"):
                filename = filename[len("backend/"):]
            path = backend_path / filename
        elif frontend_path.exists() and ext in FRONTEND_EXTENSIONS:
            if filename.startswith("frontend/"):
                filename = filename[len("frontend/"):]
            path = frontend_path / filename
        else:
            path = project_path / filename

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            code,
            encoding="utf-8"
        )

        print(
            f"Updated: {filename}"
        )