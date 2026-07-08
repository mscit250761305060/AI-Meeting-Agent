from agents.ai_file_generator_agent import (
    generate_file
)


def build_project(
    requirements,
    output_folder
):

    files = [

        (
            "app.py",
            "Generate FastAPI backend."
        ),

        (
            "models.py",
            "Generate SQLAlchemy models."
        ),

        (
            "database.py",
            "Generate database connection."
        ),

        (
            "schemas.py",
            "Generate Pydantic schemas."
        ),

        (
            "requirements.txt",
            "Generate Python requirements."
        )

    ]

    for filename, instruction in files:

        generate_file(

            requirements,

            filename,

            instruction,

            output_folder

        )