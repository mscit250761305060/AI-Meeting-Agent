import shutil
from pathlib import Path


def generate_demo_project(plan):

    template_name = plan["template"]

    template_path = Path(
        f"templates/{template_name}"
    )

    output_path = Path(
        f"generated_projects/{template_name}_demo"
    )

    if output_path.exists():
        shutil.rmtree(output_path)

    shutil.copytree(
        template_path,
        output_path
    )

    return {
        "status": "success",
        "project_path": str(output_path)
    }