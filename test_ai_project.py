from agents.ai_file_writer_agent import (
    write_generated_files
)
from agents.ai_project_generator_agent import (
    generate_project_structure
)

response = generate_project_structure(
    requirements,
    "generated_projects/employee_management_demo"
)

write_generated_files(
    response,
    "generated_projects/employee_management_demo"
)