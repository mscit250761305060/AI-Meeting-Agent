import json

from agents.ai_project_builder_agent import (
    build_project
)

with open(
    "data/requirements.json",
    "r",
    encoding="utf-8"
) as f:

    requirements = json.load(f)

build_project(

    requirements,

    "generated_projects/employee_management_demo"

)