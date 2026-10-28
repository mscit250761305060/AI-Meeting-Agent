import shutil
from pathlib import Path


def generate_demo_project(plan):
    template_name = plan.get("template", "app")
    template_path = Path(f"templates/{template_name}")
    output_path = Path(f"generated_projects/{template_name}_demo")

    if not output_path.exists():
        if template_path.exists():
            shutil.copytree(template_path, output_path)
            print("Project created from template.")
        else:
            output_path.mkdir(parents=True, exist_ok=True)
            print(f"Project directory {output_path} initialized.")
    else:
        print("Existing project found. Skipping template copy.")

    return {
        "status": "success",
        "project_path": str(output_path)
    }