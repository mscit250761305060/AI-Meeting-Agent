from pathlib import Path


def generate_crud_app(requirements, project_path):

    """
    Step 33

    CRUD generator currently does not overwrite app.py.

    In future it will generate separate API route files.

    """

    project_path = Path(project_path)

    print("CRUD Generator: Skipped app.py generation.")

    return {
        "status": "crud_ready"
    }