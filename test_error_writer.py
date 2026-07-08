from agents.error_file_writer_agent import (
    overwrite_project_files
)

response = """
{
    "app.py":"print('Fixed by AI')",

    "requirements.txt":"fastapi\\nuvicorn"
}
"""

overwrite_project_files(

    response,

    "generated_projects/employee_management_demo"

)