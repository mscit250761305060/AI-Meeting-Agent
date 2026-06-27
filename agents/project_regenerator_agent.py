import json
import time
from pathlib import Path

from agents.project_planner_agent import (
    plan_project
)

from agents.code_generator_agent import (
    generate_demo_project
)

from agents.file_generator_agent import (
    generate_project_files
)

from agents.crud_generator_agent import (
    generate_crud_app
)

from agents.page_generator_agent import (
    generate_pages
)

from agents.ui_generator_agent import (
    generate_ui
)

from agents.frontend_generator_agent import (
    generate_frontend
)


def start_project_regenerator():

    requirements_file = Path(
        "data/requirements.json"
    )

    last_content = ""

    print(
        "Project Regenerator Started..."
    )

    while True:

        try:

            if requirements_file.exists():

                content = requirements_file.read_text(
                    encoding="utf-8"
                )

                if (
                    content.strip()
                    and content != last_content
                ):

                    print(
                        "\nRequirements Changed"
                    )

                    requirements = json.loads(
                        content
                    )
                    if "error" in requirements:

                        print(
                            "Invalid requirements file. Skipping..."
                        )

                        last_content = content
                        continue

                    print("\nFULL REQUIREMENTS:")
                    print(requirements)
                    print(type(requirements))

                    plan = plan_project(
                        requirements
                    )

                    project = generate_demo_project(
                        plan
                    )

                    generate_project_files(
                        requirements,
                        project["project_path"]
                    )

                    generate_crud_app(
                        requirements,
                        project["project_path"]
                    )

                    generate_ui(
                        requirements,
                        project["project_path"]
                    )

                    generate_frontend(
                        requirements,
                        project["project_path"]
                    )

                    print("Generating Pages...")
                    print(requirements.get("pages"))

                    generate_pages(
                        requirements,
                        project["project_path"]
                    )

                    print("Pages Generated")

                    print(
                        "Project Regenerated Successfully"
                    )

                    print(
                        project["project_path"]
                    )

                    last_content = content

            time.sleep(5)

        except Exception as e:

            print(
                f"Regenerator Error: {e}"
            )

            time.sleep(5)