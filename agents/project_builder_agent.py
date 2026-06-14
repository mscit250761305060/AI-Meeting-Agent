def build_project_structure(requirements):

    return {
        "project_name": requirements.get(
            "project_title",
            "demo_project"
        ),

        "folders": [
            "backend",
            "frontend",
            "database"
        ]
    }