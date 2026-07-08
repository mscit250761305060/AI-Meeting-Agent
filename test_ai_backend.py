import json

from agents.ai_backend_generator_agent import (
    generate_backend
)

with open(
    "data/requirements.json",
    "r",
    encoding="utf-8"
) as f:

    requirements = json.load(f)

generate_backend(

    requirements,

    "generated_projects/employee_management_demo"

)