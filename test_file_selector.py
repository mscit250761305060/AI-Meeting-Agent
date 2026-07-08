from agents.file_selector_agent import (
    find_related_files
)

files = find_related_files(

    "generated_projects/employee_management_demo",

    "login page"

)

print(files)